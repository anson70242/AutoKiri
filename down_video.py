# down_video.py
from pathlib import Path
from src.core.pipeline import DownloadPipeline

def main():
    print("=" * 60 + "\n      🎬 AutoKiri-Flow [仅影片模式] 🎬      \n" + "=" * 60)
    url = input("\n🔗 请输入要处理的影片链接: ").strip()
    
    if url:
        pipeline = DownloadPipeline(Path(__file__).resolve().parent)
        # 开启视频下载，关闭弹幕下载
        pipeline.process(url, download_video=True, download_chat=False)

if __name__ == "__main__":
    main()