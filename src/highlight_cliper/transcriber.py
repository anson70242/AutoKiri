# src/highlight_cliper/transcriber.py
import subprocess
from pathlib import Path
from typing import Optional

class WhisperTranscriber:
    """调用 Faster-Whisper-XXL 进行语音转文字的包装器"""

    def __init__(self, exe_path: Path):
        self.exe_path = exe_path

    def transcribe(self, video_path: Path, language: str = "ja", model: str = "large-v3-turbo") -> Optional[Path]:
        """
        执行音频/视频转写
        :param video_path: 目标视频/音频文件路径
        :param language: 语言代码，默认 ja (日文)
        :param model: 模型大小，默认 large-v3
        :return: 成功返回生成的 .srt 文件路径，失败返回 None
        """
        if not self.exe_path.exists():
            print(f"[Error] 找不到 Faster-Whisper-XXL 执行文件: {self.exe_path}")
            return None

        if not video_path.exists():
            print(f"[Error] 找不到待转写的视频文件: {video_path}")
            return None

        output_dir = video_path.parent
        expected_srt = output_dir / f"{video_path.stem}.srt"

        # ✨ 新增逻辑：如果 SRT 已存在且不为空，直接跳过转写
        if expected_srt.exists() and expected_srt.stat().st_size > 0:
            print(f"[Info] ⏭️ 发现已存在的字幕文件，跳过转写: {expected_srt.name}")
            return expected_srt

        print(f"\n[Info] 🤖 启动 Faster-Whisper-XXL (模型: {model}, 语言: {language})")
        print(f"[Info] 正在处理: {video_path.name}")
        print(f"[Info] 这可能需要一些时间，请耐心等待...")

        # 组装 CLI 指令
        cmd = [
            str(self.exe_path),
            str(video_path),
            "--language", language,
            "--model", model,
            "--output_format", "srt", 
            "--output_dir", str(output_dir),
            
            # --- 基础参数 ---
            "--compute_type", "float16",
            "--beam_size", "5",
            "--vad_filter", "True",
            
            # --- 🔪 解决“漏句/跳句”的核心优化参数 ---
            
            # 1. 关闭上下文依赖 (绝杀大段跳句！)
            "--condition_on_previous_text", "False",
            
            # 2. 降低无语音阈值
            "--no_speech_threshold", "0.5",
            
            # 3. 拆分后的 VAD 参数 (降低阈值，保留微弱人声)
            "--vad_threshold", "0.35",
            "--vad_min_speech_duration_ms", "250",

            # 4. 开启终端进度条显示
            "--print_progress"
        ]

        try:
            # 去掉 check=True，这样即使它报错退出，Python 也不会直接抛出异常中断执行
            result = subprocess.run(cmd)
            
            if result.returncode != 0:
                print(f"[Warning] Whisper 进程退出返回码非零 ({result.returncode})，通常是显存释放时的已知 bug，正在检查输出文件...")

            # 无论是否报错退出，我们都以最终文件是否生成为唯一标准
            if expected_srt.exists() and expected_srt.stat().st_size > 0:
                print(f"[Success] 🎯 语音转写完成！字幕文件已生成: {expected_srt.name}")
                return expected_srt
            else:
                print(f"[Error] 未能在预期路径找到有效的字幕文件: {expected_srt}")
                return None
                
        except Exception as e:
            print(f"[Error] Whisper 执行过程中发生严重崩溃: {e}")
            return None