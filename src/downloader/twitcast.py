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
        生成一个包含直播链接的 txt 文件作为替代。
        """
        url = self.metadata.get("original_url")
        if not url:
            return None
            
        output_path = self.generate_output_path(suffix="_chat_link", ext="txt")
        
        if output_path.exists():
            print(f"[Info] 直播链接信息文件已存在: {output_path.name}")
            return output_path
            
        print(f"[Info] 暂不支持 TwitCasting 弹幕下载，将生成链接备忘录: {output_path.name}")
        
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"TwitCasting Stream URL:\n{url}\n")
            return output_path
        except Exception as e:
            print(f"[Error] 写入链接文件失败: {e}")
            return None