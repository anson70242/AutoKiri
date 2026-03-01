# down_video.py
import os
import traceback
from src.core import get_base_path, DownloadPipeline

def main():
    print("=" * 60 + "\n       AutoKiri-Flow [仅影片模式]       \n" + "=" * 60)
    url = input("\n 请输入要处理的影片链接: ").strip()
    
    if url:
        pipeline = DownloadPipeline(get_base_path())
        pipeline.process(url, download_video=True, download_chat=False)

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