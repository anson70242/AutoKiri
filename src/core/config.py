# src/core/config.py
import re
import yaml
from pathlib import Path

class ConfigManager:
    """全局配置与路径管理器"""
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config_data = self._load_yaml()
        self.tools_paths = self.config_data.get("tools_paths", {})
        self.streamers = self.config_data.get("streamers", [])
        self.whisper_config = self.config_data.get("whisper", {})
        self.prompts_paths = self.config_data.get("prompts", {})

    def _load_yaml(self) -> dict:
        config_path = self.project_root / "config.yaml"
        if not config_path.exists():
            print(f"[Error] 找不到配置文件: {config_path}")
            return {}
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def get_tool_exe(self, tool_name: str, default_path: str) -> Path:
        """获取工具的绝对路径"""
        rel_path = self.tools_paths.get(tool_name, default_path)
        return self.project_root / "tools" / rel_path
    
    def get_prompt_path(self, prompt_key: str) -> Path:
        """新增：获取 Prompt Markdown 文件的绝对路径"""
        rel_path = self.prompts_paths.get(prompt_key)
        if rel_path:
            return self.project_root / rel_path
        return None

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """清除 Windows 档案/文件夹名称中不允许的特殊字符"""
        return re.sub(r'[\\/*?:"<>|]', "_", name)

    def get_output_dir(self, creator: str, date_str: str, title: str) -> Path:
        """统一生成标准的输出文件夹路径: videos/streamer_name/video_date/title/"""
        safe_creator = self.sanitize_filename(creator)
        safe_date = self.sanitize_filename(date_str)
        safe_title = self.sanitize_filename(title)
        
        output_dir = self.project_root / "videos" / safe_creator / safe_date / safe_title
        # output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir