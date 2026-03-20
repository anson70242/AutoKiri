# src/trigger/twitter.py
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict

class TwitterTrigger:
    """
    Twitter (X) Space 平台的触发器逻辑。
    通过扫描个人主页推文，过滤并获取已结束的 Space 录音。
    """

    def __init__(self, ytdlp_path: Path):
        """
        :param ytdlp_path: yt-dlp 执行文件的绝对路径
        """
        self.ytdlp_path = ytdlp_path

    def get_latest_videos(self, channel_id: str, streamer_name: str, limit: int = 15) -> List[Dict[str, str]]:
        """
        获取 Twitter 主页的最新 Space
        
        :param channel_id: Twitter 的 @ 账号 ID (不带 @，例如 shino_haru101)
        :param limit: 检查的最新推文数量 (建议设大一点，因为会混杂普通推文)
        """
        url = f"https://twitter.com/{channel_id}"
        
        ready_videos = []
        seen_ids = set()
        
        # Twitter 限制严格，必须挂载浏览器 Cookie 才能顺利抓取个人主页
        cmd = [
            str(self.ytdlp_path),
            "--playlist-end", str(limit),
            "--dump-json",
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
                
                # 关键过滤：只处理 Twitter Space，跳过普通的短视频或图片推文
                extractor = video_data.get("extractor", "")
                webpage_url = video_data.get("webpage_url", "")
                
                if "twitter:space" not in extractor and "/spaces/" not in webpage_url:
                    continue
                    
                vid = video_data.get("id")
                title = video_data.get("title", "Unknown Space")
                live_status = video_data.get("live_status", "")
                
                upload_date = video_data.get("upload_date")
                if not upload_date and video_data.get("timestamp"):
                    upload_date = datetime.fromtimestamp(video_data["timestamp"]).strftime("%Y%m%d")
                    
                if not upload_date:
                    upload_date = "Unknown Date"
                
                # 过滤掉正在直播的 Space，只抓取已经结束并转为回放的 Space
                if live_status not in ["is_live", "is_upcoming"]:
                    if vid and vid not in seen_ids:
                        seen_ids.add(vid)
                        ready_videos.append({
                            "uploader": streamer_name,
                            "title": title,
                            "upload_date": upload_date,
                            "video_id": str(vid),
                            "url": webpage_url or f"https://twitter.com/{channel_id}/status/{vid}",
                            "platform": "twitter"
                        })
                        
        except subprocess.CalledProcessError as e:
            print(f"[Error] TwitterTrigger 获取主播 {streamer_name} 的列表失败: {e.stderr.strip()}")
        except Exception as e:
            print(f"[Error] TwitterTrigger 解析主播 {streamer_name} 时发生异常: {e}")
            
        return ready_videos
    
if __name__ == "__main__":
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.append(str(project_root))

    from src.core.config import ConfigManager, get_base_path

    print("-" * 50)
    print("[Test] TwitterTrigger 单次请求测试启动")
    print("-" * 50)

    base_path = get_base_path()
    config = ConfigManager(base_path)
    ytdlp_exe = config.get_tool_exe("yt_dlp", "yt-dlp/yt-dlp.exe")

    if not ytdlp_exe.exists():
        print(f"[Error] 找不到 yt-dlp 执行文件: {ytdlp_exe}")
        sys.exit(1)

    trigger = TwitterTrigger(ytdlp_path=ytdlp_exe)

    test_channel_id = None
    test_streamer_name = "Unknown"
    
    # 动态获取第一个 Twitter 频道的配置
    for streamer in config.streamers:
        for account in streamer.get("accounts", []):
            if account.get("platform") == "twitter":
                test_channel_id = account.get("channel_id") 
                test_streamer_name = streamer.get("name", "Unknown")
                break
        if test_channel_id:
            break

    if not test_channel_id:
        print("[Error] config.yaml 中没有找到任何 Twitter 频道配置。")
        sys.exit(1)
    
    print(f"[Info] 正在请求主播 {test_streamer_name} 的 Twitter 最新数据 (限制检查最新 15 条推文)...")
    
    results = trigger.get_latest_videos(channel_id=test_channel_id, streamer_name=test_streamer_name, limit=15)

    print("\n[Result] 抓取完成，返回数据如下:")
    import json
    print(json.dumps(results, indent=4, ensure_ascii=False))
    print("-" * 50)