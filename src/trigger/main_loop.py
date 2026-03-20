# src/trigger/main_loop.py
import sys
import time
import sqlite3
import logging
from pathlib import Path

# 将项目根目录加入 sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.core.config import ConfigManager, get_base_path
from src.core.pipeline import DownloadPipeline
from src.trigger.youtube import YouTubeTrigger
from src.trigger.twitch import TwitchTrigger
from src.trigger.twitcast import TwitcastTrigger
from src.core.logging_config import setup_logging, setup_trigger_logging, setup_pipeline_logging

# Setup logging
logger = setup_logging(project_root)
trigger_logger = setup_trigger_logging()
pipeline_logger = setup_pipeline_logging()

DB_FILE = Path(__file__).resolve().parent / "autokiri_history.db"
CHECK_INTERVAL_SECONDS = 300  # 默认轮询间隔 (1 分钟)
CHECK_LIMIT = 2                # 每个频道每次检查的最新影片数量

# ==========================================
# 测试模式开关：
# 设为 True 时，只获取列表，不执行下载，不写入数据库，且只执行一次
# 设为 False 时，为正式上线状态
# ==========================================
TEST_MODE = True 

# ==========================================
# 开始日期过滤：
# 格式为 YYYYMMDD (例如 "20240101")。只下载这个日期 (包含) 之后的影片。
# 设为 "" 或 None 则不限制日期，全量检查。
# ==========================================
START_DATE = "20260305"


class DatabaseManager:
    """全局 SQLite 数据库管理器，用于多平台记录去重"""
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS download_history (
                    video_id TEXT PRIMARY KEY,
                    platform TEXT,
                    uploader TEXT,
                    title TEXT,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def is_downloaded(self, video_id: str) -> bool:
        """检查该影片 ID 是否已经处理过"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM download_history WHERE video_id = ?", (video_id,))
            return cursor.fetchone() is not None

    def add_record(self, video_id: str, platform: str, uploader: str, title: str, status: str = "success"):
        """添加或更新影片处理记录"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO download_history (video_id, platform, uploader, title, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (video_id, platform, uploader, title, status))
            conn.commit()


def main():
    logger.info("AutoKiri Multi-Platform Trigger Loop 启动")
    if TEST_MODE:
        logger.info("*** 当前处于 TEST_MODE (只测试获取逻辑，不下载，不写数据库) ***")
    if START_DATE:
        logger.info(f"*** 启用日期过滤：只处理 {START_DATE} 及之后的影片 ***")

    base_path = get_base_path()
    config = ConfigManager(base_path)
    
    # 1. 初始化通用组件
    db = DatabaseManager(DB_FILE)
    pipeline = DownloadPipeline(base_path)

    # 2. 获取所需工具路径
    ytdlp_exe = config.get_tool_exe("yt_dlp", "yt-dlp/yt-dlp.exe")
    twitch_cli_exe = config.get_tool_exe("twitch_downloader_cli", "TwitchDownloaderCLI/TwitchDownloaderCLI.exe")

    if not ytdlp_exe.exists():
        print(f"[Error] 找不到 yt-dlp: {ytdlp_exe}")
        sys.exit(1)

    # 3. 注册各个平台的 Trigger
    triggers = {
        "youtube": YouTubeTrigger(ytdlp_path=ytdlp_exe),
        "twitch": TwitchTrigger(ytdlp_path=ytdlp_exe, cli_path=twitch_cli_exe, project_root=project_root),
        "twitcast": TwitcastTrigger(ytdlp_path=ytdlp_exe),
    }

    logger.info(f"数据库位置：{DB_FILE}")
    logger.info(f"当前已注册平台解析器：{list(triggers.keys())}")
    if not TEST_MODE:
        logger.info(f"轮询间隔：{CHECK_INTERVAL_SECONDS} 秒")

    # 4. 进入主循环
    while True:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        logger.info(f"=== [{current_time}] 开始本轮全平台扫描 ===")

        for streamer in config.streamers:
            streamer_name = streamer.get("name", "Unknown")
            
            for account in streamer.get("accounts", []):
                platform = account.get("platform")
                
                # 路由机制：如果当前平台我们写了对应的 Trigger，就执行
                if platform in triggers:
                    channel_id = account.get("channel_id")
                    channel_name = account.get("channel_name")
                    
                    target_id = channel_id if channel_id else channel_name
                    if not target_id:
                        continue
                        
                    logger.info(f"正在检查 [{platform}] 主播：{streamer_name} ({target_id})")
                    try:
                        latest_videos = triggers[platform].get_latest_videos(
                            channel_id=target_id, 
                            streamer_name=streamer_name, 
                            limit=CHECK_LIMIT
                        )
                    except Exception as e:
                        logger.error(f"获取 [{platform}] {streamer_name} 列表时发生异常：{e}")
                        continue

                    # 处理返回的影片列表
                    for video in latest_videos:
                        vid = video["video_id"]
                        v_title = video["title"]
                        v_url = video["url"]
                        v_date = video.get("upload_date", "")

                        # ==========================================
                        # 步骤 A：日期过滤拦截
                        # ==========================================
                        if START_DATE and v_date.isdigit() and len(v_date) == 8:
                            if v_date < START_DATE:
                                if TEST_MODE:
                                    logger.info(f"  -> [Skip] {v_title} | 日期太旧 ({v_date})")
                                continue 

                        # ==========================================
                        # 步骤 B：数据库去重判断
                        # ==========================================
                        if not db.is_downloaded(vid):
                            logger.info(f"  -> 发现新内容待处理：{v_title} ({vid}) [日期：{v_date}]")
                            
                            # 测试模式拦截
                            if TEST_MODE:
                                logger.info(f"     [Test] URL: {v_url} | 测试模式已拦截，跳过真实下载。")
                                continue 
                            
                            try:
                                # 触发下载管线
                                logger.info(f"     [Info] 开始执行下载管线...")
                                pipeline.process(url=v_url, download_video=True, download_chat=True)
                                
                                # 下载成功，写入数据库
                                db.add_record(
                                    video_id=vid, 
                                    platform=platform, 
                                    uploader=streamer_name, 
                                    title=v_title, 
                                    status="success"
                                )
                                logger.info(f"     [Info] 影片已记录至数据库：{vid}")
                                
                            except Exception as e:
                                logger.error(f"     [Error] 处理影片 {vid} 时发生严重异常：{e}")
                                db.add_record(
                                    video_id=vid, 
                                    platform=platform, 
                                    uploader=streamer_name, 
                                    title=v_title, 
                                    status="failed"
                                )
            else:
                pass
        
        # 测试模式只跑一轮就强制退出
        if TEST_MODE:
            logger.info("=== 测试模式单次扫描结束，程序退出 ===")
            break

        logger.info(f"=== 本轮扫描结束，休眠 {CHECK_INTERVAL_SECONDS} 秒 ===")
        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("用户手动终止了监控程序。")
    except Exception as e:
        logger.error(f"监控模块发生崩溃：{e}")
