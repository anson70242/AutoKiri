# src/post_process/youtube_chat_parser.py
import json
import math
from pathlib import Path

def format_seconds(total_seconds: float) -> str:
    h = math.floor(total_seconds / 3600)
    m = math.floor((total_seconds % 3600) / 60)
    s = math.floor(total_seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def parse_youtube_chat(input_path: Path, output_path: Path) -> bool:
    if not input_path.exists():
        print(f"[Error] 找不到输入文件: {input_path}")
        return False

    parsed_chat = []

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    
                    actions = item.get('replayChatItemAction', {}).get('actions', [])
                    if not actions:
                        continue
                    
                    item_data = actions[0].get('addChatItemAction', {}).get('item', {}).get('liveChatTextMessageRenderer')
                    if not item_data:
                        continue
                    
                    offset_str = item.get('videoOffsetTimeMsec', '0')
                    offset_sec = int(offset_str) / 1000.0
                    time_str = format_seconds(offset_sec)
                    
                    user = item_data.get('authorName', {}).get('simpleText', 'Unknown')
                    
                    msg = ""
                    runs = item_data.get('message', {}).get('runs', [])
                    for r in runs:
                        if 'text' in r:
                            msg += r['text']
                        elif 'emoji' in r:
                            shortcuts = r['emoji'].get('shortcuts', [])
                            if shortcuts:
                                msg += shortcuts[0]
                    
                    if msg.strip():
                        parsed_chat.append({"time": time_str, "user": user, "msg": msg})
                        
                except json.JSONDecodeError:
                    continue

        if not parsed_chat:
            print("[Warning] YouTube: 未提取到任何有效的弹幕数据。")
            return False

        # 定制化输出：强制让 time, user, msg 在同一行
        lines = [f'  {json.dumps(c, ensure_ascii=False)}' for c in parsed_chat]
        custom_json_output = "[\n" + ",\n".join(lines) + "\n]"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(custom_json_output)

        print(f"[Success] YouTube 弹幕清洗完成，共提取 {len(parsed_chat)} 条")
        return True

    except Exception as e:
        print(f"[Error] YouTube 清洗弹幕发生致命错误: {e}")
        return False