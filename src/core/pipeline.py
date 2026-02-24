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
from src.highlight_cliper.srt_splitter import SrtSplitter

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

        creator = metadata.get("creator", "Unknown")
        title = metadata.get("title", "UnknownTitle")

        # 👇 拦截机制：如果是 Unknown，极大概率是 Cookie 失效被墙了
        if creator == "Unknown":
            print(f"\n[Warning] ⚠️ 识别到未知的实况主或异常标题: {title}")
            print("如果这是会限影片，这通常意味着你的 Cookie / Token 已失效！")
            ans = input("❓ 是否仍要继续创建文件夹并尝试下载？(y/N): ").strip().lower()
            if ans != 'y':
                print("[Info] 任务已取消，不会产生任何多余的空文件夹。")
                return {}

        output_dir = self.config.get_output_dir(
            creator,
            metadata.get("date", "UnknownDate"),
            title
        )
        
        # 👇 延迟创建：只有通过了上面的拦截，才真正建立文件夹
        output_dir.mkdir(parents=True, exist_ok=True)
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
             
             # 👇 自动清理机制：如果下载组件彻底失败，且没留下任何文件，就删掉空文件夹
             try:
                 if output_dir.exists() and not any(output_dir.iterdir()):
                     output_dir.rmdir()
                     # 尝试连同上一级的日期文件夹一并清理
                     if not any(output_dir.parent.iterdir()):
                         output_dir.parent.rmdir()
                     print(f"[Info] 已自动清理下载失败产生的空文件夹。")
             except Exception:
                 pass
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
        
        srt_path = transcriber.transcribe(
            video_path, 
            whisper_config=self.config.whisper_config
        )

        #  =========== 新增：步骤 2 字幕切割与 Prompt 部署 =========== 
        split_files = []
        if srt_path and Path(srt_path).exists():
            print("\n" + "-" * 60)
            print(">>> [AI 管线 - 步骤 2] 均分字幕文件与部署 Prompt ...")
            print("-" * 60)
            
            splitter = SrtSplitter(max_blocks=500)
            split_files = splitter.split_srt(Path(srt_path))
            
            # 读取 config 中配置的 Prompt 路径
            prompt_analyze = self.config.get_prompt_path("speech_analyze")
            prompt_sentence = self.config.get_prompt_path("to_excel")
            
            valid_prompts = [p for p in [prompt_analyze, prompt_sentence] if p is not None]
            
            # 部署 Prompt 到和 SRT 相同的资料夹下
            splitter.copy_prompts(Path(srt_path).parent, valid_prompts)
        #  ========================================================= 

        return {
            "srt_path": srt_path,
            "split_srt_paths": split_files
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
            if not chat_path:
                print("\n[Info] ⚠️ 弹幕文件缺失，AI 分析将仅依赖 Whisper 语音识别结果进行。")
            self.highlighter.process(video_path, chat_path)
            
        print("\n" + "=" * 60)
        print(f"🎉 一条龙任务全部执行完毕！")
        print("=" * 60)