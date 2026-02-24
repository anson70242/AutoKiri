# src/downloader/youtube.py
import os
from pathlib import Path
from typing import Optional

from .base import BaseDownloader

class YoutubeDownloader(BaseDownloader):
    """YouTube 平台专用的下载器"""

    def download_video(self) -> Optional[Path]:
        url = self.metadata.get("original_url")
        if not url:
            print("[Error] 找不到原始 URL，无法下载视频")
            return None
            
        ytdlp_exe = self.get_tool_path("yt_dlp")
        ffmpeg_exe = self.get_tool_path("ffmpeg")
        
        output_path = self.generate_output_path(ext="mp4")
        
        if output_path.exists():
            print(f"[Info] 视频文件已存在，跳过下载: {output_path.name}")
            return output_path
            
        print(f"[Info] 开始下载 YouTube 视频: {url}")
        
        # 基础命令 (不包含 Cookie)
        base_command = [
            str(ytdlp_exe),
            "--rm-cache-dir",
            "--ffmpeg-location", str(ffmpeg_exe),
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "--js-runtimes", "node",
            "-N", "5",
            "-o", str(output_path),
            url
        ]
        
        # 1. 尝试无 Cookie 下载
        print("[Info] 尝试普通下载模式...")
        success = self.run_command(base_command)
        
        # 2. 如果失败，尝试挂载 Cookie 重新下载
        if not success:
            cookie_file = self.project_root / "secret" / "youtube_cookies.txt"
            if cookie_file.exists():
                print("[Warning] 普通下载失败(可能为会员限定或年龄限制)，尝试挂载 youtube_cookie.txt 重试...")
                # 将 --cookies 参数插入到 url 前面
                retry_command = base_command[:-1] + ["--cookies", str(cookie_file), url]
                success = self.run_command(retry_command, env=custom_env)
            else:
                print("[Error] 下载失败，且未找到 youtube_cookie.txt 提供权限。")
        
        # 检查最终结果
        if success and output_path.exists():
            print(f"[Success] 视频下载成功: {output_path.name}")
            return output_path
            
        print("[Error] 视频下载最终失败")
        return None

    def download_chat(self) -> Optional[Path]:
        url = self.metadata.get("original_url")
        if not url:
            print("[Error] 找不到原始 URL，无法下载弹幕")
            return None
            
        ytdlp_exe = self.get_tool_path("yt_dlp")
        
        base_output_template = self.generate_output_path(suffix="_chat", ext="%(ext)s")
        expected_live_chat_path = self.generate_output_path(suffix="_chat", ext="live_chat.json")
        
        if expected_live_chat_path.exists():
            print(f"[Info] 弹幕文件已存在，跳过下载: {expected_live_chat_path.name}")
            return expected_live_chat_path

        print(f"[Info] 开始抓取 YouTube 聊天室/字幕: {url}")
        
        # 基础命令 (不包含 Cookie)
        base_command = [
            str(ytdlp_exe),
            "--skip-download",          
            "--write-subs",              
            "--sub-lang", "live_chat", 
            "--js-runtimes", "node",
            "-o", str(base_output_template),
            url
        ]
        
        # 1. 尝试无 Cookie 获取弹幕
        print("[Info] 尝试普通模式获取弹幕...")
        success = self.run_command(base_command)
        
        # 2. 如果失败，尝试挂载 Cookie 重新获取
        if not success:
            cookie_file = self.project_root / "secret" / "youtube_cookies.txt"
            if cookie_file.exists():
                print("[Warning] 获取弹幕失败，尝试挂载 youtube_cookie.txt 重试...")
                retry_command = base_command[:-1] + ["--cookies", str(cookie_file), url]
                success = self.run_command(retry_command, env=custom_env)
            else:
                print("[Error] 弹幕获取失败，且未找到 youtube_cookie.txt。")
        
        # 验证文件是否成功生成
        possible_extensions = ["live_chat.json", "ja.vtt", "en.vtt", "json", "vtt"]
        for ext in possible_extensions:
            check_path = self.generate_output_path(suffix="_chat", ext=ext)
            if check_path.exists():
                print(f"[Success] 弹幕/字幕下载成功: {check_path.name}")
                return check_path
                
        print("[Warning] 未找到弹幕或字幕文件，可能该视频未提供。")
        return None

# === 快速测试区块 ===
if __name__ == "__main__":
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent
    
    test_output_dir = project_root / "test_output"
    
    mock_tools_paths = {
        "yt_dlp": "yt-dlp/yt-dlp.exe",
        "ffmpeg": "ffmpeg-8.0.1-essentials_build/bin/ffmpeg.exe",
        "node": "node-v24.13.1-win-x64/node.exe" 
    }
    
    # 模拟 MetadataManager 解析出来的资料
    mock_metadata = {
        "status": "success",
        "platform": "youtube",
        "creator": "Haru",
        "title": "Youtube下载测试视频",
        "date": "20260223",
        "original_url": "https://www.youtube.com/watch?v=OBNqNcLrlDQ" 
    }
    
    downloader = YoutubeDownloader(
        project_root=project_root,
        metadata=mock_metadata,
        output_dir=test_output_dir,
        tools_paths=mock_tools_paths
    )
    
    print("-" * 50)
    print("[Test] 开始测试 YoutubeDownloader")
    print("-" * 50)
    
    print("\n>>> 步骤 1: 测试下载影片")
    video_result = downloader.download_video()
        
    print("\n>>> 步骤 2: 测试下载聊天室/弹幕")
    chat_result = downloader.download_chat()