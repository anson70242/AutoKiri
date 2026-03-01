# highlight_only.py
import os
import traceback
from pathlib import Path
from src.core import get_base_path, HighlightPipeline


def main():
    print("=" * 60 + "\n       AutoKiri-Flow [仅 AI 分析模式]       \n" + "=" * 60)
    
    # 直接要求输入本地已经下载好的 mp4 绝对路径
    video_input = input("\n 请输入本地影片的绝对路径 (例如 C:\\...\\video.mp4): ").strip()
    # 过滤掉路径两边可能带有的双引号（从文件夹复制路径时常见）
    video_input = video_input.strip('"') 
    
    if video_input:
        video_path = Path(video_input)
        pipeline = HighlightPipeline(get_base_path())
        pipeline.process(video_path)

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