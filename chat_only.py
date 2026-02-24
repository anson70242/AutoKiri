
# chat_only.py
import os
import re
import yaml
from pathlib import Path

from src.downloader.metadata import MetadataManager
from src.downloader.youtube import YoutubeDownloader
from src.downloader.twitch import TwitchDownloader
from src.post_process.youtube_chat_parser import YoutubeChatParser
from src.post_process.twitch_chat_parser import TwitchChatParser

def load_tools_paths(project_root: Path) -> dict:
    """读取 config.yaml 获取工具路径"""
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        print("[Error] 找不到 config.yaml！")
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        return config.get("tools_paths", {})

def sanitize_filename(name: str) -> str:
    """清除 Windows 档案/文件夹名称中不允许的特殊字符"""
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def main():
    print("=" * 60)
    print("      💬 AutoKiri-Flow [仅弹幕模式] 💬      ")
    print("=" * 60)

    # 1. 基础环境配置
    project_root = Path(__file__).resolve().parent
    tools_paths = load_tools_paths(project_root)

    # 2. 获取用户输入
    url = input("\n🔗 请输入要处理的影片链接 (YouTube/Twitch): ").strip()
    if not url:
        print("[Error] 链接不能为空，程序退出。")
        return

    # 3. 解析 Metadata
    print("\n" + "-" * 60)
    print(">>> [步骤 1/3] 解析影片元数据 (Metadata) ...")
    print("-" * 60)
    
    metadata_manager = MetadataManager(project_root)
    metadata = metadata_manager.analyze(url)
    
    if metadata["status"] != "success":
        print("[Error] Metadata 解析失败，请检查链接或网络状态并更新cookies。")
        return
        
    platform = metadata["platform"]
    creator = metadata.get("creator", "Unknown")
    date_str = metadata.get("date", "UnknownDate")
    title = metadata.get("title", "UnknownTitle")

    print(f"[Info] 平台: {platform}")
    print(f"[Info] 创作者: {creator}")
    print(f"[Info] 标题: {title}")
    print(f"[Info] 日期: {date_str}")

    # 动态生成专属的分类资料夹
    safe_creator = sanitize_filename(creator)
    safe_date = sanitize_filename(date_str)
    safe_title = sanitize_filename(title)
    
    output_dir = project_root / "videos" / safe_creator / safe_date / safe_title
    output_dir.mkdir(parents=True, exist_ok=True) 
    
    print(f"[Info] 设定保存路径: {output_dir}")

    # 4. 初始化对应的下载器和弹幕解析器
    if platform == "youtube":
        downloader = YoutubeDownloader(project_root, metadata, output_dir, tools_paths)
        chat_parser = YoutubeChatParser()
    elif platform == "twitch":
        downloader = TwitchDownloader(project_root, metadata, output_dir, tools_paths)
        chat_parser = TwitchChatParser()
    else:
        print(f"[Error] 暂不支持的平台: {platform}")
        return

    # 5. 执行下载 (仅弹幕)
    print("\n" + "-" * 60)
    print(">>> [步骤 2/3] 仅下载弹幕文件 ...")
    print("-" * 60)
    
    chat_path = downloader.download_chat()

    # 拦截器：如果弹幕下载失败，直接终止
    if not chat_path:
        print("\n" + "-" * 30)
        print("严重错误：弹幕未能成功下载！")
        print("请检查：")
        print("   1. 链接是否正确且为公开影片？")
        print("   2. 若为会员限定，secret/youtube_cookies.txt 是否已过期？")
        print("   3. 影片本身是否有关闭聊天室重播？")
        print("-" * 30 + "\n")
        return  

    # 6. 弹幕后处理 (Post-process Chat)
    print("\n" + "-" * 60)
    print(">>> [步骤 3/3] 清洗弹幕文件 ...")
    print("-" * 60)
    
    if chat_path and chat_path.exists():
        parsed_chat_path = chat_path.with_name(chat_path.name.replace("_chat", "_chat_parsed"))
        parsed_chat_path = parsed_chat_path.with_suffix(".json") 
        chat_parser.parse(chat_path, parsed_chat_path)
    else:
        print("[Warning] 跳过弹幕清洗，因为找不到原始弹幕文件。")

    print("\n" + "=" * 60)
    print(f"🎉 弹幕任务执行完毕！档案已保存在:\n{output_dir}")
    print("=" * 60)

if __name__ == "__main__":
    main()