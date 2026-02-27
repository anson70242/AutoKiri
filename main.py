# main.py
import os
import traceback
from src.core.config import get_base_path
from src.core.pipeline import TotalPipeline

def main():
    print("=" * 60 + "\n       AutoKiri-Flow [全流程]       \n" + "=" * 60)
    url = input("\n 请输入链接: ").strip()
    if url:
        pipeline = TotalPipeline(get_base_path())
        pipeline.process(url)

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