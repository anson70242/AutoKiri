# src/core/pipeline.py
from pathlib import Path
from src.core.config import ConfigManager
from src.downloader.metadata import MetadataManager
from src.downloader.youtube import YoutubeDownloader
from src.downloader.twitch import TwitchDownloader
from src.downloader.twitcast import TwitcastDownloader
from src.post_process.youtube_chat_parser import YoutubeChatParser
from src.post_process.twitch_chat_parser import TwitchChatParser
from src.post_process.video_splitter import VideoSplitter

class AutoKiriPipeline:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config = ConfigManager(project_root)
        self.metadata_manager = MetadataManager(project_root)

    def process(self, url: str, download_video: bool = True):
        """
        执行主流程
        :param download_video: True 代表全套流程，False 代表仅弹幕模式
        """
        print("\n" + "-" * 60)
        print(">>> [步骤 1] 解析影片元数据 (Metadata) ...")
        print("-" * 60)
        
        metadata = self.metadata_manager.analyze(url)
        if metadata["status"] != "success":
            print("[Error] Metadata 解析失败，程序终止。")
            return

        # 获取统一管理的输出目录
        output_dir = self.config.get_output_dir(
            metadata.get("creator", "Unknown"),
            metadata.get("date", "UnknownDate"),
            metadata.get("title", "UnknownTitle")
        )
        print(f"[Info] 设定保存路径: {output_dir}")

        # 动态分配下载器和解析器
        platform = metadata["platform"]
        tools_paths_dict = self.config.tools_paths # 兼容旧代码的传参

        if platform == "youtube":
            downloader = YoutubeDownloader(self.project_root, metadata, output_dir, tools_paths_dict)
            chat_parser = YoutubeChatParser()
        elif platform == "twitch":
            downloader = TwitchDownloader(self.project_root, metadata, output_dir, tools_paths_dict)
            chat_parser = TwitchChatParser()
        elif platform == "twitcast":
            downloader = TwitcastDownloader(self.project_root, metadata, output_dir, tools_paths_dict)
            chat_parser = None # TwitCasting 没有 JSON 弹幕需要清洗
        else:
            print(f"[Error] 暂不支持的平台: {platform}")
            return

        # 执行下载
        print("\n" + "-" * 60)
        print(">>> [步骤 2] 执行下载任务 ...")
        print("-" * 60)
        
        video_path = downloader.download_video() if download_video else None
        chat_path = downloader.download_chat()

        if not chat_path and (download_video and not video_path):
             print("[Error] 影片和弹幕均下载失败！提前终止。")
             return

        # 执行清洗
        print("\n" + "-" * 60)
        print(">>> [步骤 3] 清洗弹幕文件 ...")
        print("-" * 60)
        
        # 执行清洗
        print("\n" + "-" * 60)
        print(">>> [步骤 3] 清洗弹幕文件 ...")
        print("-" * 60)
        
        # 修正：chat_parser が存在する場合（Noneではない場合）のみ parse を実行する
        if chat_parser and chat_path and chat_path.exists():
            parsed_chat_path = chat_path.with_name(chat_path.name.replace("_chat", "_chat_parsed")).with_suffix(".json") 
            chat_parser.parse(chat_path, parsed_chat_path)
        else:
            print("[Info] 当前平台无需或暂不支持 JSON 弹幕清洗，已跳过。")

        # 仅在完整模式下切片
        if download_video:
            print("\n" + "-" * 60)
            print(">>> [步骤 4] 检查并切割超大影片 ...")
            print("-" * 60)
            if video_path and video_path.exists():
                ffmpeg_exe = self.config.get_tool_exe("ffmpeg", "ffmpeg-8.0.1-essentials_build/bin/ffmpeg.exe")
                ffprobe_exe = self.config.get_tool_exe("ffprobe", "ffmpeg-8.0.1-essentials_build/bin/ffprobe.exe")
                splitter = VideoSplitter(ffmpeg_exe, ffprobe_exe, max_size_gb=10.0)
                splitter.split(video_path)

        print("\n" + "=" * 60)
        print(f"🎉 任务执行完毕！档案已保存在:\n{output_dir}")
        print("=" * 60)