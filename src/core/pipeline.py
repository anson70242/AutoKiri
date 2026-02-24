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
from src.highlight_cliper.transcriber import WhisperTranscriber

class DownloadPipeline:
    """专职负责：解析 Metadata -> 下载影片与弹幕 -> 弹幕清洗 -> 影片切割"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config = ConfigManager(project_root)
        self.metadata_manager = MetadataManager(project_root)

    def process(self, url: str, download_video: bool = True) -> dict:
        print("\n" + "-" * 60)
        print(">>> [下载管线 - 步骤 1] 解析影片元数据 ...")
        print("-" * 60)
        
        metadata = self.metadata_manager.analyze(url)
        if metadata["status"] != "success":
            print("[Error] Metadata 解析失败，程序终止。")
            return {}

        output_dir = self.config.get_output_dir(
            metadata.get("creator", "Unknown"),
            metadata.get("date", "UnknownDate"),
            metadata.get("title", "UnknownTitle")
        )
        print(f"[Info] 设定保存路径: {output_dir}")

        platform = metadata["platform"]
        tools_paths_dict = self.config.tools_paths

        # 分配下载器
        if platform == "youtube":
            downloader = YoutubeDownloader(self.project_root, metadata, output_dir, tools_paths_dict)
            chat_parser = YoutubeChatParser()
        elif platform == "twitch":
            downloader = TwitchDownloader(self.project_root, metadata, output_dir, tools_paths_dict)
            chat_parser = TwitchChatParser()
        elif platform == "twitcast":
            downloader = TwitcastDownloader(self.project_root, metadata, output_dir, tools_paths_dict)
            chat_parser = None 
        else:
            print(f"[Error] 暂不支持的平台: {platform}")
            return {}

        print("\n" + "-" * 60)
        print(">>> [下载管线 - 步骤 2] 执行下载任务 ...")
        print("-" * 60)
        
        video_path = downloader.download_video() if download_video else None
        chat_path = downloader.download_chat()

        if not chat_path and (download_video and not video_path):
             print("[Error] 影片和弹幕均未能获取！提前终止。")
             return {}

        print("\n" + "-" * 60)
        print(">>> [下载管线 - 步骤 3] 清洗弹幕文件 ...")
        print("-" * 60)
        
        parsed_chat_path = None
        if chat_parser and chat_path and chat_path.exists():
            parsed_chat_path = chat_path.with_name(chat_path.name.replace("_chat", "_chat_parsed")).with_suffix(".json") 
            chat_parser.parse(chat_path, parsed_chat_path)
        else:
            print("[Info] 当前平台无需或暂不支持 JSON 弹幕清洗，已跳过。")
            if chat_path and chat_path.exists():
                parsed_chat_path = chat_path # TwitCasting 的 txt 备忘录

        if download_video and video_path and video_path.exists():
            print("\n" + "-" * 60)
            print(">>> [下载管线 - 步骤 4] 检查并切割超大影片 ...")
            print("-" * 60)
            ffmpeg_exe = self.config.get_tool_exe("ffmpeg", "ffmpeg-8.0.1-essentials_build/bin/ffmpeg.exe")
            ffprobe_exe = self.config.get_tool_exe("ffprobe", "ffmpeg-8.0.1-essentials_build/bin/ffprobe.exe")
            splitter = VideoSplitter(ffmpeg_exe, ffprobe_exe, max_size_gb=10.0)
            splitter.split(video_path)

        return {
            "output_dir": output_dir,
            "video_path": video_path,
            "chat_path": parsed_chat_path
        }


class HighlightPipeline:
    """专职负责：提取音频文字 (Whisper) -> 结合弹幕生成 Prompt -> 请求 LLM (预留)"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config = ConfigManager(project_root)

    def process(self, video_path: Path, chat_path: Path = None) -> dict:
        if not video_path or not video_path.exists():
            print("[Error] 影片文件不存在，无法执行 AI 分析。")
            return {}

        print("\n" + "-" * 60)
        print(">>> [AI 管线 - 步骤 1] 语音识别 (Faster-Whisper) ...")
        print("-" * 60)
        
        whisper_exe = self.config.get_tool_exe("faster_whisper", "faster-whisper-xxl/faster-whisper-xxl.exe")
        transcriber = WhisperTranscriber(whisper_exe)
        
        # 调用大模型生成 SRT
        srt_path = transcriber.transcribe(video_path, language="ja", model="large-v3-turbo")

        # 预留：步骤 2 - 结合 srt_path 和 chat_path 构建 Prompt
        # 预留：步骤 3 - 发送给 LLM 获取高光时间轴

        return {
            "srt_path": srt_path
        }


class TotalPipeline:
    """一条龙服务：串联 Download 和 Highlight"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.downloader = DownloadPipeline(project_root)
        self.highlighter = HighlightPipeline(project_root)

    def process(self, url: str):
        # 1. 先跑下载
        download_results = self.downloader.process(url, download_video=True)
        
        video_path = download_results.get("video_path")
        chat_path = download_results.get("chat_path")

        # 2. 如果视频下载成功，无缝衔接跑 AI 分析
        if video_path:
            self.highlighter.process(video_path, chat_path)
            
        print("\n" + "=" * 60)
        print(f"🎉 一条龙任务全部执行完毕！")
        print("=" * 60)