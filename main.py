# main.py
from pathlib import Path
from src.core.pipeline import TotalPipeline

def main():
    print("=" * 60 + "\n      🚀 AutoKiri-Flow [全流程] 🚀      \n" + "=" * 60)
    url = input("\n🔗 请输入链接: ").strip()
    if url:
        pipeline = TotalPipeline(Path(__file__).resolve().parent)
        pipeline.process(url)

if __name__ == "__main__":
    main()