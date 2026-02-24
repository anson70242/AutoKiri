from pathlib import Path
from src.core.pipeline import AutoKiriPipeline

def main():
    print("=" * 60 + "\n      💬 AutoKiri-Flow [仅弹幕模式] 💬      \n" + "=" * 60)
    url = input("\n🔗 请输入要处理的影片链接: ").strip()
    if url:
        pipeline = AutoKiriPipeline(Path(__file__).resolve().parent)
        pipeline.process(url, download_video=False)  # 关键差异：这里传 False

if __name__ == "__main__":
    main()