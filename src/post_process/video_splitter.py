# src/post_process/video_splitter.py
import os
import math
import subprocess
from pathlib import Path

class VideoSplitter:
    def __init__(self, ffmpeg_path: Path, ffprobe_path: Path, max_size_gb: float = 10.0):
        """
        初始化视频分割器
        :param ffmpeg_path: ffmpeg 执行文件路径
        :param ffprobe_path: ffprobe 执行文件路径
        :param max_size_gb: 触发分割的默认大小阈值 (GB)
        """
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self.max_size_gb = max_size_gb

    def _get_video_duration(self, video_path: Path) -> float:
        """内部方法：使用 ffprobe 获取视频总时长（秒）"""
        cmd = [
            str(self.ffprobe_path),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())

    def split(self, video_path: Path, max_size_gb: float = None) -> bool:
        """
        执行分割
        """
        if not video_path.exists():
            print(f"[Error] 找不到输入文件: {video_path}")
            return False

        # 允许在调用时覆盖默认的 max_size_gb
        limit_gb = max_size_gb if max_size_gb is not None else self.max_size_gb
        max_size_bytes = limit_gb * 1024 * 1024 * 1024
        file_size = os.path.getsize(video_path)

        if file_size <= max_size_bytes:
            print(f"[Info] 影片大小 ({file_size / 1024**3:.2f} GB) 未超过 {limit_gb} GB，不需切割。")
            return True

        num_parts = math.ceil(file_size / max_size_bytes)
        print(f"[Info] 影片大小 ({file_size / 1024**3:.2f} GB) 超过限制，准备等分为 {num_parts} 段。")

        try:
            duration = self._get_video_duration(video_path)
        except Exception as e:
            print(f"[Error] 无法获取影片长度，切割失败: {e}")
            return False

        segment_time = duration / num_parts
        output_dir = video_path.parent
        base_name = video_path.name
        output_template = output_dir / f"[P%d]{base_name}"
        
        print(f"[Info] 开始执行切割，每段长度约为 {segment_time:.2f} 秒...")

        cmd = [
            str(self.ffmpeg_path),
            "-i", str(video_path),
            "-c", "copy",
            "-f", "segment",
            "-segment_time", str(segment_time),
            "-segment_start_number", "1",
            "-reset_timestamps", "1",
            str(output_template)
        ]

        try:
            subprocess.run(cmd, check=True)
            print(f"[Success] 影片切割完成！原档案 {base_name} 已保留。")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[Error] 影片切割过程发生错误: {e}")
            return False

# === 快速测试区块 ===
if __name__ == "__main__":
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent
    
    # 从你的工具目录对应路径
    test_ffmpeg_path = project_root / "tools" / "ffmpeg-8.0.1-essentials_build" / "bin" / "ffmpeg.exe"
    test_ffprobe_path = project_root / "tools" / "ffmpeg-8.0.1-essentials_build" / "bin" / "ffprobe.exe"
    test_video_path = project_root / "test_output" / "[20260223][Haru] Youtube下载测试视频.mp4"

    if not test_ffmpeg_path.exists() or not test_ffprobe_path.exists():
        print("[Error] 找不到 ffmpeg 或 ffprobe，请检查 config.yaml 及 tools 目录。")
        exit(1)

    if not test_video_path.exists():
        print(f"[Warning] 测试影片 {test_video_path.name} 不存在，如果你要独立测试，请建立一个虚拟文件或修改路径。")
    else:
        print("-" * 50)
        print("[Test] 开始测试 Video Splitter (Class 模式)")
        print("-" * 50)
        
        # 实例化 Splitter，为了测试方便把阈值设为 1.5GB（也可以传其他较小的值测试）
        splitter = VideoSplitter(test_ffmpeg_path, test_ffprobe_path, max_size_gb=1.5)
        success = splitter.split(test_video_path)