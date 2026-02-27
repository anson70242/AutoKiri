# down_chat.py
import os
import traceback
from src.core.config import get_base_path
from src.core.pipeline import DownloadPipeline

def main():
    print("=" * 60 + "\n       AutoKiri-Flow [仅弹幕模式]       \n" + "=" * 60)
    url = input("\n 请输入要处理的影片链接: ").strip()

    if url:
        pipeline = DownloadPipeline(get_base_path())
        pipeline.process(url, download_video=False, download_chat=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n" + "!" * 60)
        print("❌ [致命错误] 程序运行中发生崩溃：")
        traceback.print_exc() 
        print("!" * 60)
    finally:
        print("\n")
        os.system("pause")