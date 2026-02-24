# src/highlight_cliper/transcriber.py
import subprocess
from pathlib import Path
from typing import Optional

class WhisperTranscriber:
    """调用 Faster-Whisper-XXL 进行语音转文字的包装器"""

    def __init__(self, exe_path: Path):
        self.exe_path = exe_path

    # 👇 修改：将 language 和 model 参数替换为 whisper_config
    def transcribe(self, video_path: Path, whisper_config: dict = None) -> Optional[Path]:
        if whisper_config is None:
            whisper_config = {}

        if not self.exe_path.exists():
            print(f"[Error] 找不到 Faster-Whisper-XXL 执行文件: {self.exe_path}")
            return None

        if not video_path.exists():
            print(f"[Error] 找不到待转写的视频文件: {video_path}")
            return None

        output_dir = video_path.parent
        expected_srt = output_dir / f"{video_path.stem}.srt"

        if expected_srt.exists() and expected_srt.stat().st_size > 0:
            print(f"[Info] ⏭️ 发现已存在的字幕文件，跳过转写: {expected_srt.name}")
            return expected_srt

        # 👇 动态读取配置
        language = whisper_config.get("language", "ja")
        model = whisper_config.get("model", "large-v3-turbo")

        print(f"\n[Info] 🤖 启动 Faster-Whisper-XXL (模型: {model}, 语言: {language})")
        print(f"[Info] 正在处理: {video_path.name}")
        print(f"[Info] 这可能需要一些时间，请耐心等待...")

        # 👇 动态组装 CLI 指令，注意转成 str() 防止类型错误
        cmd = [
            str(self.exe_path),
            str(video_path),
            "--language", language,
            "--model", model,
            "--output_format", "srt", 
            "--output_dir", str(output_dir),
            
            # --- 基础参数 ---
            "--compute_type", str(whisper_config.get("compute_type", "float16")),
            "--beam_size", str(whisper_config.get("beam_size", 5)),
            "--vad_filter", str(whisper_config.get("vad_filter", True)),
            
            # --- 🔪 解决“漏句/跳句”的核心优化参数 ---
            "--condition_on_previous_text", str(whisper_config.get("condition_on_previous_text", False)),
            "--no_speech_threshold", str(whisper_config.get("no_speech_threshold", 0.5)),
            "--vad_threshold", str(whisper_config.get("vad_threshold", 0.35)),
            "--vad_min_speech_duration_ms", str(whisper_config.get("vad_min_speech_duration_ms", 250)),

            # 4. 开启终端进度条显示
            "--print_progress"
        ]

        try:
            result = subprocess.run(cmd)
            
            if result.returncode != 0:
                print(f"[Warning] Whisper 进程退出返回码非零 ({result.returncode})，通常是显存释放时的已知 bug，正在检查输出文件...")

            if expected_srt.exists() and expected_srt.stat().st_size > 0:
                print(f"[Success] 🎯 语音转写完成！字幕文件已生成: {expected_srt.name}")
                return expected_srt
            else:
                print(f"[Error] 未能在预期路径找到有效的字幕文件: {expected_srt}")
                return None
                
        except Exception as e:
            print(f"[Error] Whisper 执行过程中发生严重崩溃: {e}")
            return None