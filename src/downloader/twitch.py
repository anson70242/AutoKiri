# src/downloader/twitch.py
import os
from pathlib import Path
import subprocess
from typing import Optional
from dotenv import load_dotenv

from .base import BaseDownloader

class TwitchDownloader(BaseDownloader):
    """Twitch 平台专用的下载器"""

    def _get_oauth_token(self) -> Optional[str]:
        """尝试从环境变量获取 Twitch OAuth Token (用于下载会员限定影片)"""
        env_path = self.project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        return os.getenv("twitch_OAuth") or os.getenv("TWITCH_OAUTH")

    def _get_custom_env(self) -> dict:
        """构造包含内置 Node.js 路径的临时环境变量"""
        env = os.environ.copy()
        try:
            node_exe = self.get_tool_path("node")
            node_dir = os.path.dirname(str(node_exe))
            env["PATH"] = f"{node_dir}{os.pathsep}{env.get('PATH', '')}"
        except Exception:
            pass
        return env

    def download_video(self) -> Optional[Path]:
        url = self.metadata.get("original_url")
        if not url:
            print("[Error] 找不到原始 URL，无法下载视频")
            return None
            
        cli_exe = self.get_tool_path("twitch_downloader_cli")
        ffmpeg_exe = self.get_tool_path("ffmpeg")
        
        output_path = self.generate_output_path(ext="mp4")
        
        if output_path.exists():
            print(f"[Info] 视频文件已存在，跳过下载: {output_path.name}")
            return output_path
            
        print(f"[Info] 开始下载 Twitch 视频: {url}")
        
        # 组装 TwitchDownloaderCLI 视频下载命令
        command = [
            str(cli_exe), "videodownload",
            "--id", url,
            "--ffmpeg-path", str(ffmpeg_exe),
            "--collision", "Overwrite",  # 避免命令行卡在询问是否覆盖的提示上
            "-o", str(output_path)
        ]
        
        # 如果有 OAuth Token，则加入命令中以支持会限影片
        oauth_token = self._get_oauth_token()
        if oauth_token:
            print("[Info] 检测到 Twitch OAuth Token，将以授权身份下载。")
            command.extend(["--oauth", oauth_token])
            
        if self.run_command(command):
            if output_path.exists():
                print(f"[Success] 视频下载成功: {output_path.name}")
                return output_path
        
        print("[Error] 视频下载失败")
        return None

    def download_chat(self) -> Optional[Path]:
        url = self.metadata.get("original_url")
        if not url:
            print("[Error] 找不到原始 URL，无法下载弹幕")
            return None
            
        cli_exe = self.get_tool_path("twitch_downloader_cli")
        
        output_path = self.generate_output_path(suffix="_chat", ext="json")
        
        if output_path.exists():
            print(f"[Info] 弹幕文件已存在，跳过下载: {output_path.name}")
            check_path = output_path
        else:
            print(f"[Info] 开始抓取 Twitch 聊天室弹幕: {url}")
            
            # 组装 TwitchDownloaderCLI 弹幕下载命令
            command = [
                str(cli_exe), "chatdownload",
                "--id", url,
                "--embed-images",  # 嵌入 Twitch 官方表情
                "--bttv=true",     # 嵌入 BetterTTV 表情
                "--ffz=true",      # 嵌入 FrankerFaceZ 表情
                "--stv=true",      # 嵌入 7TV 表情
                "--collision", "Overwrite",
                "-o", str(output_path)
            ]
            
            self.run_command(command)
            check_path = output_path

        # 检查下载结果
        if check_path.exists():
            print(f"[Success] 弹幕下载成功: {check_path.name}")
            return check_path
            
        print("[Error] 弹幕获取失败。")
        return None

# === 快速测试区块 ===
if __name__ == "__main__":
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent
    test_output_dir = project_root / "test_output"
    
    mock_tools_paths = {
        "twitch_downloader_cli": "TwitchDownloaderCLI/TwitchDownloaderCLI.exe",
        "ffmpeg": "ffmpeg-8.0.1-essentials_build/bin/ffmpeg.exe",
        "node": "node-v24.13.1-win-x64/node.exe" 
    }
    
    # 请填入一个你想测试的 Twitch VOD 或 Clip 网址
    test_url = "https://www.twitch.tv/videos/2696644813"
    
    mock_metadata = {
        "status": "success",
        "platform": "twitch",
        "creator": "Yuka",
        "title": "Twitch下载测试视频",
        "date": "20260223",
        "original_url": test_url
    }
    
    downloader = TwitchDownloader(
        project_root=project_root,
        metadata=mock_metadata,
        output_dir=test_output_dir,
        tools_paths=mock_tools_paths
    )
    
    print("-" * 50)
    print("[Test] 开始测试 TwitchDownloader")
    print("-" * 50)
    
    print("\n>>> 步骤 1: 测试下载影片")
    video_result = downloader.download_video()
        
    print("\n>>> 步骤 2: 测试下载聊天室/弹幕")
    chat_result = downloader.download_chat()