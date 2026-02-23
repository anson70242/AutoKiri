import subprocess
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

class MetadataExtractor:
    """負責在下載前輕量級地獲取影片 Metadata 並與 config.yaml 進行匹配"""
    
    def __init__(self, project_root: Path):
        self.ytdlp_exe = project_root / "tools" / "yt-dlp.exe"
        self.config_path = project_root / "config.yaml"
        self.streamers = self._load_config()

    def _load_config(self) -> list:
        """讀取 YAML 中的 streamers 設定"""
        if not self.config_path.exists():
            print("⚠️ 找不到 config.yaml，請確認檔案位置。")
            return []
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config.get("streamers", [])

    def fetch_info(self, url: str) -> Optional[Dict]:
        """呼叫 yt-dlp -j 獲取 JSON 格式的原始影片資訊 (不下載影片)"""
        if not self.ytdlp_exe.exists():
            print(f"❌ 找不到執行檔: {self.ytdlp_exe}")
            return None
        
        print(f"🔍 正在獲取影片資訊: {url}")
        # --no-warnings 確保 stdout 只有乾淨的 JSON 字串
        command = [str(self.ytdlp_exe), "-j", "--no-warnings", url]
        
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True, encoding="utf-8")
            return json.loads(result.stdout)
        except subprocess.CalledProcessError:
            print("❌ yt-dlp 執行失敗，請檢查網址是否有效或影片是否設為公開。")
            return None
        except json.JSONDecodeError:
            print("❌ JSON 解析失敗，yt-dlp 回傳格式異常。")
            return None

    def analyze(self, url: str) -> Dict:
        """分析原始資料，萃取出: 平台、創作者、標題、日期"""
        raw_data = self.fetch_info(url)
        if not raw_data:
            return {"status": "error"}

        # 1. 判斷平台 (正規化 yt-dlp 的 extractor_key)
        extractor = raw_data.get("extractor_key", "").lower()
        if "youtube" in extractor:
            platform = "youtube"
        elif "twitch" in extractor:
            platform = "twitch"
        elif "twitcast" in extractor:
            platform = "twitcast"
        else:
            platform = "unknown"

        # 2. 判斷影片創作者 (與 config.yaml 匹配)
        channel_id = raw_data.get("channel_id", "")
        # Twitch 或 TwitCasting 的帳號 ID 通常會出現在 uploader_id 或 uploader
        uploader_id = raw_data.get("uploader_id", "").lower()
        uploader = raw_data.get("uploader", "").lower()
        
        creator_name = "Unknown"

        for streamer in self.streamers:
            for account in streamer.get("accounts", []):
                # 確認平台一致
                if account.get("platform") == platform:
                    
                    # YouTube 邏輯: 精準匹配 channel_id
                    if platform == "youtube" and account.get("channel_id") == channel_id:
                        creator_name = streamer["name"]
                        break
                        
                    # Twitch / TwitCasting 邏輯: 匹配 channel_name
                    elif platform in ["twitch", "twitcast"]:
                        target_name = account.get("channel_name", "").lower()
                        if target_name in [uploader_id, uploader]:
                            creator_name = streamer["name"]
                            break
                            
            if creator_name != "Unknown":
                break

        # 3. 獲取標題 (清理可能導致檔名錯誤的特殊字元可以留到後面處理)
        title = raw_data.get("title", "No Title")

        # 4. 獲取日期 (轉成 YYYYMMDD 格式，方便後續做檔名)
        timestamp = raw_data.get("timestamp")
        if timestamp:
            # 直播通常有精準的 Unix timestamp
            date_str = datetime.fromtimestamp(timestamp).strftime("%Y%m%d")
        else:
            # 一般影片只有 upload_date (YYYYMMDD)
            date_str = raw_data.get("upload_date", "19700101")

        return {
            "status": "success",
            "platform": platform,
            "creator": creator_name,
            "title": title,
            "date": date_str,
            "original_url": url
        }

# === 快速測試區塊 ===
if __name__ == "__main__":
    # 動態取得專案根目錄 (假設這支程式放在 src/downloader/metadata.py)
    project_root = Path(__file__).resolve().parent.parent.parent
    
    extractor = MetadataExtractor(project_root)
    
    # 你可以替換成 Yuka 或 Haru 的 YouTube/Twitch/Twitcasting 測試網址
    test_urls = [
        "https://www.youtube.com/watch?v=YOUR_TEST_URL", 
    ]
    
    for target_url in test_urls:
        print("-" * 40)
        result = extractor.analyze(target_url)
        
        if result["status"] == "success":
            print(f"🎬 平台: {result['platform']}")
            print(f"👤 創作者: {result['creator']}")
            print(f"📅 日期: {result['date']}")
            print(f"📝 標題: {result['title']}")
            
            # 💡 這裡可以直接組合成超完美的自動化檔名！
            safe_title = "".join(c for c in result['title'] if c not in r'\/:*?"<>|') # 去除不可做檔名的字元
            suggested_filename = f"{result['date']}_{result['creator']}_{safe_title}.mp4"
            print(f"\n✨ 建議儲存檔名: {suggested_filename}")