# src/downloader/base.py
import os
import re
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional

class BaseDownloader(ABC):
    """所有平台下载器的抽象基类 (支持视频与聊天室弹幕分离下载)"""
    
    def __init__(self, project_root: Path, metadata: Dict, output_dir: Path, tools_paths: Dict, download_settings: Dict = None):
        """
        初始化下载器
        :param project_root: 项目根目录 Path
        :param metadata: 由 MetadataManager 获取到的元数据字典
        :param output_dir: 文件保存的输出目录 Path
        :param tools_paths: config.yaml 中的 tools_paths 字典
        :param download_settings: config.yaml 中的 download_settings 字典 (新增)
        """
        self.project_root = project_root
        self.metadata = metadata
        self.output_dir = output_dir
        self.tools_paths = tools_paths
        self.download_settings = download_settings or {} # 保存下载设置
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def download_video(self) -> Optional[Path]:
        """
        下载视频文件的核心方法。
        子类必须实现此方法。
        :return: 下载成功返回视频文件的完整 Path，失败返回 None
        """
        pass

    @abstractmethod
    def download_chat(self) -> Optional[Path]:
        """
        下载聊天室/弹幕的核心方法。
        子类必须实现此方法。
        :return: 下载成功返回弹幕文件的完整 Path，失败返回 None
        """
        pass

    def download_all(self) -> Dict[str, Optional[Path]]:
        """
        一键调度：依次下载视频和聊天室记录
        :return: 包含 video 和 chat 路径的字典
        """
        print(f"开始处理: {self.metadata.get('title')}")
        
        video_path = self.download_video()
        chat_path = self.download_chat()
        
        return {
            "video": video_path,
            "chat": chat_path
        }

    def get_tool_path(self, tool_key: str) -> Path:
        """
        获取内置工具的绝对路径并验证文件是否存在。
        例如: self.get_tool_path("yt_dlp")
        """
        tool_rel_path = self.tools_paths.get(tool_key)
        if not tool_rel_path:
            raise ValueError(f"在配置中找不到工具路径: {tool_key}")
            
        tool_path = self.project_root / "tools" / tool_rel_path
        if not tool_path.exists():
            raise FileNotFoundError(f"工具文件不存在: {tool_path}")
            
        return tool_path

    def generate_output_path(self, suffix: str = "", ext: str = "mp4") -> Path:
        """
        根据 metadata 统一生成标准化的输出文件路径。
        :param suffix: 文件名后缀，例如 "_chat"
        :param ext: 文件副档名，例如 "mp4" 或 "json"
        
        示例输出: 
        - 视频: [20250109][Yuka] 直播标题.mp4 (suffix="", ext="mp4")
        - 弹幕: [20250109][Yuka] 直播标题_chat.json (suffix="_chat", ext="json")
        """
        date_str = self.metadata.get("date", "19700101")
        creator = self.metadata.get("creator", "Unknown")
        title = self.metadata.get("title", "No Title")
        
        # 清理 Windows/Linux 文件名中的非法字符
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
        # 去除多余空格
        safe_title = " ".join(safe_title.split())
        
        filename = f"[{date_str}][{creator}] {safe_title}{suffix}.{ext}"
        return self.output_dir / filename
    
    def run_command(self, command: list, env: Optional[Dict[str, str]] = None) -> bool:
        """
        公共的命令行执行辅助方法
        :param command: 命令列表
        :param env: 临时环境变量字典 (可选)
        """
        try:
            print(f"[Exec] 执行命令: {' '.join(str(c) for c in command)}")
            # 将 env 传给 subprocess
            subprocess.run(command, check=True, env=env)
            return True
        except subprocess.CalledProcessError as e:
            print(f"[Error] 命令执行失败，返回码: {e.returncode}")
            return False