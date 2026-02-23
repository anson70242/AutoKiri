# src/post_process/twitch_chat_parser.py
import json
import math
from pathlib import Path

def format_seconds(total_seconds: float) -> str:
    h = math.floor(total_seconds / 3600)
    m = math.floor((total_seconds % 3600) / 60)
    s = math.floor(total_seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def parse_twitch_chat(input_path: Path, output_path: Path) -> bool:
    if not input_path.exists():
        print(f"[Error] 找不到输入文件: {input_path}")
        return False

    parsed_chat = []

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            
        for c in json_data.get('comments', []):
            offset = c.get('contentOffsetSeconds', 0)
            time_str = format_seconds(offset)
            
            user = c.get('commenter', {}).get('displayName', 'Unknown')
            msg = c.get('message', {}).get('body', '')
            
            if msg.strip():
                parsed_chat.append({"time": time_str, "user": user, "msg": msg})

        if not parsed_chat:
            print("[Warning] Twitch: 未提取到任何有效的弹幕数据。")
            return False

        # 定制化输出：强制让 time, user, msg 在同一行
        lines = [f'  {json.dumps(c, ensure_ascii=False)}' for c in parsed_chat]
        custom_json_output = "[\n" + ",\n".join(lines) + "\n]"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(custom_json_output)

        print(f"[Success] Twitch 弹幕清洗完成，共提取 {len(parsed_chat)} 条")
        return True

    except Exception as e:
        print(f"[Error] Twitch 清洗弹幕发生致命错误: {e}")
        return False