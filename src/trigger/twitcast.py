# src/trigger/twitcast.py
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict

class TwitcastTrigger:
    """
    TwitCasting 平台的触发器逻辑。
    使用 yt-dlp 获取 TwitCasting 频道的历史直播录像列表。
    """

    def __init__(self, ytdlp_path: Path):
        """
        :param ytdlp_path: yt-dlp 执行文件的绝对路径
        """
        self.ytdlp_path = ytdlp_path

    def get_latest_videos(self, channel_id: str, streamer_name: str, limit: int = 5) -> List[Dict[str, str]]:
        """
        获取 TwitCasting 频道的最新回放录像
        
        :param channel_id: TwitCasting 的账号 ID (例如 shino_nome22)
        :param streamer_name: 从 config 获取的主播名字
        :param limit: 检查的最新数量
        """
        # TwitCasting 的历史回放列表统一在 /show/ 路径下
        url = f"https://twitcasting.tv/{channel_id}/show/"
        
        ready_videos = []
        seen_ids = set()
        
        # 组装 yt-dlp 命令，进行深度解析以获取完整信息
        cmd = [
            str(self.ytdlp_path),
            "--playlist-end", str(limit),
            "--dump-json",
            # 加入 Firefox Cookie，以便获取会员限定或带密码的录像列表
            "--cookies-from-browser", "firefox",
            url
        ]
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True, 
                encoding="utf-8"
            )
            
            lines = result.stdout.strip().split('\n')
            
            for line in lines:
                if not line.strip():
                    continue
                
                try:
                    video_data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                    
                vid = video_data.get("id")
                title = video_data.get("title", "Unknown Title")
                live_status = video_data.get("live_status", "")
                
                # 获取日期：TwitCasting 解析通常会返回 timestamp
                upload_date = video_data.get("upload_date")
                if not upload_date and video_data.get("timestamp"):
                    upload_date = datetime.fromtimestamp(video_data["timestamp"]).strftime("%Y%m%d")
                    
                if not upload_date:
                    upload_date = "Unknown Date"

                # 组装播放链接
                v_url = video_data.get("webpage_url")
                if not v_url and vid:
                    v_url = f"https://twitcasting.tv/{channel_id}/movie/{vid}"
                
                # 过滤掉正在直播的，只抓已结束的录像
                if live_status not in ["is_live", "is_upcoming"]:
                    if vid and vid not in seen_ids:
                        seen_ids.add(vid)
                        ready_videos.append({
                            "uploader": streamer_name,
                            "title": title,
                            "upload_date": upload_date,
                            "video_id": str(vid),
                            "url": v_url or f"https://twitcasting.tv/{channel_id}/movie/{vid}",
                            "platform": "twitcast"
                        })
                        
        except subprocess.CalledProcessError as e:
            print(f"[Error] TwitcastTrigger 获取主播 {streamer_name} 的列表失败: {e.stderr.strip()}")
        except Exception as e:
            print(f"[Error] TwitcastTrigger 解析主播 {streamer_name} 时发生异常: {e}")
            
        return ready_videos
    
if __name__ == "__main__":
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.append(str(project_root))

    from src.core.config import ConfigManager, get_base_path

    print("-" * 50)
    print("[Test] TwitcastTrigger 单次请求测试启动")
    print("-" * 50)

    base_path = get_base_path()
    config = ConfigManager(base_path)
    ytdlp_exe = config.get_tool_exe("yt_dlp", "yt-dlp/yt-dlp.exe")

    if not ytdlp_exe.exists():
        print(f"[Error] 找不到 yt-dlp 执行文件: {ytdlp_exe}")
        sys.exit(1)

    trigger = TwitcastTrigger(ytdlp_path=ytdlp_exe)

    test_channel_id = None
    test_streamer_name = "Unknown"
    
    # 动态获取第一个 TwitCasting 频道的配置
    for streamer in config.streamers:
        for account in streamer.get("accounts", []):
            if account.get("platform") == "twitcast":
                test_channel_id = account.get("channel_name") 
                test_streamer_name = streamer.get("name", "Unknown")
                break
        if test_channel_id:
            break

    if not test_channel_id:
        print("[Error] config.yaml 中没有找到任何 TwitCasting 频道配置。")
        sys.exit(1)
    
    print(f"[Info] 正在请求主播 {test_streamer_name} 的 TwitCasting 最新数据...")
    
    results = trigger.get_latest_videos(channel_id=test_channel_id, streamer_name=test_streamer_name, limit=3)

    print("\n[Result] 抓取完成，返回数据如下:")
    import json
    print(json.dumps(results, indent=4, ensure_ascii=False))
    print("-" * 50)