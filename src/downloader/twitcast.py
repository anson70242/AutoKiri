# src/downloader/twitcast.py
import os
from pathlib import Path
from typing import Optional

from .base import BaseDownloader

class TwitcastDownloader(BaseDownloader):
    """TwitCasting 平台专用的下载器"""

    def download_video(self) -> Optional[Path]:
        url = self.metadata.get("original_url")
        if not url:
            print("[Error] 找不到原始 URL，无法下载 TwitCasting 视频")
            return None
            
        ytdlp_exe = self.get_tool_path("yt_dlp")
        ffmpeg_exe = self.get_tool_path("ffmpeg")
        
        output_path = self.generate_output_path(ext="mp4")
        
        if output_path.exists():
            print(f"[Info] 视频文件已存在，跳过下载: {output_path.name}")
            return output_path
            
        print(f"[Info] 开始下载 TwitCasting 视频: {url}")
        
        command = [
            str(ytdlp_exe),
            "--rm-cache-dir",
            "--js-runtimes", "node",                  
            "--ffmpeg-location", str(ffmpeg_exe),    
            "--hls-use-mpegts",
            "--write-comments", 
            "--merge-output-format", "mp4",
            "-o", str(output_path),
            url
        ]
        
        if self.run_command(command):
            if output_path.exists():
                print(f"[Success] TwitCasting 视频下载成功: {output_path.name}")
                return output_path
        
        print("[Error] TwitCasting 视频下载失败")
        return None

    def download_chat(self) -> Optional[Path]:
        """
        由于已在 Pipeline 层统一生成备忘录，此处直接跳过弹幕处理。
        """
        print("[Info] TwitCasting 暂不支持弹幕下载，已跳过。")
        return None