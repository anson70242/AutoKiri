# src/downloader/twitter.py
import os
from pathlib import Path
from typing import Optional

from .base import BaseDownloader

class TwitterDownloader(BaseDownloader):
    """Twitter (X) Space 专用的下载器"""

    def download_video(self) -> Optional[Path]:
        url = self.metadata.get("original_url")
        if not url:
            print("[Error] 找不到原始 URL，无法下载 Twitter Space")
            return None
            
        ytdlp_exe = self.get_tool_path("yt_dlp")
        ffmpeg_exe = self.get_tool_path("ffmpeg")
        
        # Twitter Space 是纯音频，这里强制提取并保存为 wav 格式
        output_path = self.generate_output_path(ext="wav")
        
        if output_path.exists():
            print(f"[Info] 音频文件已存在，跳过下载: {output_path.name}")
            return output_path
            
        print(f"[Info] 开始下载 Twitter Space: {url}")
        
        # 基础命令：使用 yt-dlp 抓取
        base_command = [
            str(ytdlp_exe),
            "--rm-cache-dir",
            "--ffmpeg-location", str(ffmpeg_exe),
            "--extract-audio", 
            "--audio-format", "wav",
            "-o", str(output_path),
            url
        ]
        
        # 1. 尝试无 Cookie 下载
        print("[Info] 尝试普通下载模式...")
        success = self.run_command(base_command)
        
        # 2. 如果失败，尝试挂载 Cookie 重新下载 (针对锁推/仅限关注者可见的 Space)
        if not success:
            print("[Warning] 普通下载失败，尝试从 Firefox 读取 Cookie 重试...")
            retry_command = base_command[:-1] + ["--cookies-from-browser", "firefox", url]
            success = self.run_command(retry_command)
            
        if success and output_path.exists():
            print(f"[Success] Twitter Space 下载成功: {output_path.name}")
            return output_path
            
        print("[Error] Twitter Space 下载最终失败")
        return None

    def download_chat(self) -> Optional[Path]:
        """
        由于已在 Pipeline 层统一生成备忘录，此处直接跳过。
        """
        print("[Info] Twitter Space 无弹幕抓取支持，已跳过。")
        return None