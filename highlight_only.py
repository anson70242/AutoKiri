# highlight_only.py
from pathlib import Path
from src.core.pipeline import HighlightPipeline

def main():
    print("=" * 60 + "\n      🧠 AutoKiri-Flow [仅 AI 分析模式] 🧠      \n" + "=" * 60)
    
    # 直接要求输入本地已经下载好的 mp4 绝对路径
    video_input = input("\n📁 请输入本地影片的绝对路径 (例如 C:\\...\\video.mp4): ").strip()
    # 过滤掉路径两边可能带有的双引号（从文件夹复制路径时常见）
    video_input = video_input.strip('"') 
    
    if video_input:
        video_path = Path(video_input)
        pipeline = HighlightPipeline(Path(__file__).resolve().parent)
        pipeline.process(video_path)

if __name__ == "__main__":
    main()