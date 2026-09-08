# src/highlight_cliper/transcriber.py
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

# SRT 时间轴行: 00:01:23,456 --> 00:01:25,789
TIMELINE_RE = re.compile(
    r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})'
)
# 以空行分割字幕块（兼容 Windows/Linux 换行符）
BLOCK_SPLIT_RE = re.compile(r'\r?\n[ \t]*\r?\n')


class WhisperTranscriber:
    """调用 Faster-Whisper-XXL 进行语音转文字的包装器

    长直播（数小时）必须分片转写：faster-whisper 会把整条音频解成一整块 float32
    数组，再对它一次性做 STFT（中间态是 complex64），这两块内存都与时长成正比。
    9 小时的素材光 STFT 就要连续分配 5GB 以上，必然爆内存。
    分片之后峰值只跟单片时长有关，与直播总长无关。
    """

    def __init__(self, exe_path: Path, ffmpeg_path: Path = None, ffprobe_path: Path = None):
        self.exe_path = exe_path
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path

    # ---------------- 音频前处理 ----------------

    def _probe_duration(self, media_path: Path) -> Optional[float]:
        """用 ffprobe 取媒体总时长（秒）"""
        cmd = [
            str(self.ffprobe_path),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(media_path)
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            print(f"[Warning] 无法取得影片长度: {e}")
            return None

    def _extract_audio(self, video_path: Path, out_wav: Path) -> bool:
        """抽成 16kHz 单声道 PCM。ffmpeg 流式处理，内存是常数。

        -vn 丢掉视频流，省掉 Whisper 自己解析容器的开销；
        -ac 1 -ar 16000 直接产出 Whisper 的目标采样格式，省掉重采样。
        """
        print(f"[Info] 正在抽取 16kHz 单声道音轨 ...")
        cmd = [
            str(self.ffmpeg_path), "-y",
            "-hide_banner", "-loglevel", "error", "-nostats",
            "-i", str(video_path),
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            "-c:a", "pcm_s16le",
            str(out_wav)
        ]
        try:
            subprocess.run(cmd, check=True)
            size_gb = out_wav.stat().st_size / 1024 ** 3
            print(f"[Success] 音轨抽取完成 ({size_gb:.2f} GB): {out_wav.name}")
            return True
        except Exception as e:
            print(f"[Error] 音轨抽取失败: {e}")
            return False

    def _split(self, full_wav: Path, work_dir: Path,
               chunk_sec: int, overlap_sec: int) -> List[Tuple[Path, float]]:
        """把整条 wav 切成多片，每片结尾多切 overlap_sec 秒。

        多切的尾巴是为了让被切口截断的那句话，在下一片里有完整的版本；
        合并时不去重，所以接缝处会有几句重复，这是刻意的取舍。

        回传 [(片路径, 该片起始的绝对秒数), ...]。
        对 PCM WAV，-ss 放在 -i 之前是按字节偏移的精确 seek，所以偏移就是 i*chunk_sec。
        """
        duration = self._probe_duration(full_wav)
        if not duration:
            return []

        num_chunks = max(1, math.ceil(duration / chunk_sec))
        print(f"[Info] 音轨总长 {duration / 3600:.2f} 小时，"
              f"按每片 {chunk_sec // 60} 分钟切成 {num_chunks} 段 "
              f"(每片结尾多切 {overlap_sec} 秒)")

        chunks = []
        for i in range(num_chunks):
            start = i * chunk_sec
            # 最后一片没有下一片，不需要多切
            length = chunk_sec if i == num_chunks - 1 else chunk_sec + overlap_sec
            chunk_path = work_dir / f"chunk_{i:03d}.wav"

            cmd = [
                str(self.ffmpeg_path), "-y",
                "-hide_banner", "-loglevel", "error", "-nostats",
                "-ss", str(start),
                "-t", str(length),
                "-i", str(full_wav),
                "-c", "copy",
                str(chunk_path)
            ]
            try:
                subprocess.run(cmd, check=True)
            except Exception as e:
                print(f"[Error] 切割第 {i + 1} 段失败: {e}")
                return []

            if not chunk_path.exists() or chunk_path.stat().st_size == 0:
                print(f"[Error] 第 {i + 1} 段切割后为空: {chunk_path.name}")
                return []

            chunks.append((chunk_path, float(start)))

        return chunks

    # ---------------- Whisper 调用 ----------------

    def _build_cmd(self, audio_path: Path, output_dir: Path, whisper_config: dict) -> list:
        """组装 Faster-Whisper-XXL 的 CLI 指令"""
        return [
            str(self.exe_path),
            str(audio_path),
            "--language", whisper_config.get("language", "ja"),
            "--model", whisper_config.get("model", "large-v3-turbo"),
            "--output_format", "srt",
            "--output_dir", str(output_dir),

            # --- 基础参数 ---
            "--compute_type", str(whisper_config.get("compute_type", "float16")),
            "--beam_size", str(whisper_config.get("beam_size", 5)),
            "--vad_filter", str(whisper_config.get("vad_filter", True)),

            # --- 解决“漏句/跳句”的核心优化参数 ---
            "--condition_on_previous_text", str(whisper_config.get("condition_on_previous_text", False)),
            "--no_speech_threshold", str(whisper_config.get("no_speech_threshold", 0.5)),
            "--vad_threshold", str(whisper_config.get("vad_threshold", 0.35)),
            "--vad_min_speech_duration_ms", str(whisper_config.get("vad_min_speech_duration_ms", 250)),

            # 4. 开启终端进度条显示
            "--print_progress"
        ]

    def _run_whisper(self, audio_path: Path, output_dir: Path, whisper_config: dict) -> Optional[Path]:
        """对单一音档跑 Whisper，回传产出的 SRT 路径"""
        expected = output_dir / f"{audio_path.stem}.srt"

        # 已经转过就跳过（分片任务中断后重跑不用从头再来）
        if expected.exists() and expected.stat().st_size > 0:
            print(f"[Info] 已存在字幕，跳过: {expected.name}")
            return expected

        try:
            result = subprocess.run(self._build_cmd(audio_path, output_dir, whisper_config))
            if result.returncode != 0:
                print(f"[Warning] Whisper 进程退出返回码非零 ({result.returncode})，"
                      f"通常是显存释放时的已知 bug，正在检查输出文件...")
        except Exception as e:
            print(f"[Error] Whisper 执行过程中发生严重崩溃: {e}")
            return None

        if expected.exists() and expected.stat().st_size > 0:
            return expected

        print(f"[Error] 未能在预期路径找到有效的字幕文件: {expected}")
        return None

    # ---------------- SRT 合并 ----------------

    @staticmethod
    def _format_ts(seconds: float) -> str:
        if seconds < 0:
            seconds = 0.0
        ms = int(round(seconds * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def _parse_blocks(srt_path: Path, offset: float) -> List[Tuple[float, float, str]]:
        """读一份分片 SRT，回传 [(绝对起始秒, 绝对结束秒, 正文), ...]"""
        content = srt_path.read_text(encoding="utf-8").strip()
        if not content:
            return []

        blocks = []
        for raw in BLOCK_SPLIT_RE.split(content):
            lines = raw.strip().split("\n")
            if len(lines) < 2:
                continue
            m = TIMELINE_RE.search(raw)
            if not m:
                continue

            g = [int(x) for x in m.groups()]
            start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0 + offset
            end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0 + offset

            # 时间轴行之后的都是字幕正文
            text_lines = []
            for i, line in enumerate(lines):
                if TIMELINE_RE.search(line):
                    text_lines = lines[i + 1:]
                    break
            text = "\n".join(text_lines).strip()
            if text:
                blocks.append((start, end, text))

        return blocks

    def _merge(self, items: List[Tuple[Path, float]], output_path: Path) -> bool:
        """把各分片的 SRT 加上时间偏移合并成一份完整字幕。

        items = [(该片的 srt, 该片起始的绝对秒数), ...]

        单纯按顺序拼接：每片的时间轴加上自己的偏移，然后重新连续编号。
        因为每片都多切了一小段尾巴，接缝处会有几句重复——刻意不做去重，
        重复对后续处理无害，而任何去重规则都有误删真实内容的风险。
        """
        count = 0
        try:
            # 边读边写，一次只处理一片
            with open(output_path, "w", encoding="utf-8") as out:
                for srt_path, offset in items:
                    for start, end, text in self._parse_blocks(srt_path, offset):
                        count += 1
                        out.write(f"{count}\n")
                        out.write(f"{self._format_ts(start)} --> {self._format_ts(end)}\n")
                        out.write(f"{text}\n\n")

        except Exception as e:
            print(f"[Error] 合并字幕时发生错误: {e}")
            return False

        # 写入已完成，收尾的打印不该影响合并结果
        print(f"[Success] 字幕合并完成，共 {count} 句对话")
        return count > 0

    # ---------------- 主流程 ----------------

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
            print(f"[Info] 发现已存在的字幕文件，跳过转写: {expected_srt.name}")
            return expected_srt

        model = whisper_config.get("model", "large-v3-turbo")
        language = whisper_config.get("language", "ja")
        chunk_minutes = whisper_config.get("chunk_minutes", 30)
        overlap_sec = int(whisper_config.get("overlap_seconds", 10))

        print(f"\n[Info] 启动 Faster-Whisper-XXL (模型: {model}, 语言: {language})")
        print(f"[Info] 正在处理: {video_path.name}")

        # chunk_minutes = 0 -> 关闭分片，走旧的整档路径（逃生阀，长片会爆内存）
        can_chunk = bool(chunk_minutes) and self.ffmpeg_path and self.ffprobe_path
        if not can_chunk:
            if chunk_minutes:
                print("[Warning] 未提供 ffmpeg/ffprobe 路径，退回整档转写模式。")
            print(f"[Info] 这可能需要一些时间，请耐心等待...")
            srt = self._run_whisper(video_path, output_dir, whisper_config)
            if srt:
                print(f"[Success] 语音转写完成！字幕文件已生成: {srt.name}")
            return srt

        return self._transcribe_chunked(
            video_path, expected_srt, whisper_config,
            int(chunk_minutes) * 60, overlap_sec
        )

    def _transcribe_chunked(self, video_path: Path, expected_srt: Path,
                            whisper_config: dict, chunk_sec: int,
                            overlap_sec: int) -> Optional[Path]:
        work_dir = video_path.parent / f".whisper_{video_path.stem}"
        full_wav = work_dir / "full.wav"

        try:
            work_dir.mkdir(parents=True, exist_ok=True)

            # 1. 抽 16kHz 单声道音轨
            if not (full_wav.exists() and full_wav.stat().st_size > 0):
                if not self._extract_audio(video_path, full_wav):
                    return None

            # 2. 按时长切片（每片多切一段重叠尾巴）
            chunks = self._split(full_wav, work_dir, chunk_sec, overlap_sec)
            if not chunks:
                print("[Error] 音轨切片失败，终止转写。")
                return None

            # 3. 逐片转写
            items, missing = [], []
            for i, (chunk_path, offset) in enumerate(chunks):
                print(f"\n[Info] 转写第 {i + 1}/{len(chunks)} 段 "
                      f"({self._format_ts(offset)} 起) ...")
                srt = self._run_whisper(chunk_path, work_dir, whisper_config)
                if srt:
                    items.append((srt, offset))
                else:
                    missing.append((offset, offset + chunk_sec))

            # 4. 有缺片就不产出正式字幕，避免残缺字幕流进下游
            if missing:
                print(f"\n[Error] 有 {len(missing)} 段未能转写成功，不产出字幕文件：")
                for start, end in missing:
                    print(f"        缺失区间 {self._format_ts(start)} ~ {self._format_ts(end)}")
                print(f"[Info] 中间文件保留在: {work_dir}")
                return None

            # 5. 合并
            if not self._merge(items, expected_srt):
                print("[Error] 字幕合并失败。")
                return None

            print(f"[Success] 语音转写完成！字幕文件已生成: {expected_srt.name}")
            return expected_srt

        except Exception as e:
            print(f"[Error] 分片转写过程中发生严重崩溃: {e}")
            return None

        finally:
            # 只有成功产出字幕才清理中间文件
            if expected_srt.exists() and expected_srt.stat().st_size > 0:
                shutil.rmtree(work_dir, ignore_errors=True)
