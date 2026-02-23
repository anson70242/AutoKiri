# src/post_process/twitch_chat_parser.py
import json
import math
from pathlib import Path

class TwitchChatParser:
    def __init__(self):
        pass

    def _format_seconds(self, total_seconds: float) -> str:
        h = math.floor(total_seconds / 3600)
        m = math.floor((total_seconds % 3600) / 60)
        s = math.floor(total_seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def parse(self, input_path: Path, output_path: Path) -> bool:
        if not input_path.exists():
            print(f"[Error] 找不到输入文件: {input_path}")
            return False

        parsed_chat = []

        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
                
            for c in json_data.get('comments', []):
                offset = c.get('content_offset_seconds', 0)
                time_str = self._format_seconds(offset)
                
                commenter = c.get('commenter') or {}
                user = commenter.get('display_name', 'Unknown')
                
                msg = c.get('message', {}).get('body', '')
                
                if msg.strip():
                    parsed_chat.append({"time": time_str, "user": user, "msg": msg})

            if not parsed_chat:
                print("[Warning] Twitch: 未提取到任何有效的弹幕数据。")
                return False

            lines = [f'  {json.dumps(c, ensure_ascii=False)}' for c in parsed_chat]
            custom_json_output = "[\n" + ",\n".join(lines) + "\n]"

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(custom_json_output)

            print(f"[Success] Twitch 弹幕清洗完成，共提取 {len(parsed_chat)} 条")
            return True

        except Exception as e:
            print(f"[Error] Twitch 清洗弹幕发生致命错误: {e}")
            return False

# === 快速测试区块 ===
if __name__ == "__main__":
    import os
    from pathlib import Path

    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent
    test_output_dir = project_root / "test_output"

    if not test_output_dir.exists():
        print(f"[Error] 找不到测试输出目录: {test_output_dir}")
        exit(1)

    chat_files = list(test_output_dir.glob("*_chat*.json"))
    
    if not chat_files:
        print(f"[Error] 在 {test_output_dir} 中找不到任何弹幕文件。")
        exit(1)

    input_file = sorted(chat_files, key=os.path.getmtime, reverse=True)[0]
    output_file = test_output_dir / f"parsed_twitch_{input_file.name}"

    print("-" * 50)
    print(f"[Test] 开始测试 Twitch Chat Parser (Class 模式)")
    print(f"> 输入文件: {input_file.name}")
    print(f"> 输出文件: {output_file.name}")
    print("-" * 50)

    # 实例化并调用
    parser = TwitchChatParser()
    success = parser.parse(input_file, output_file)

    if success and output_file.exists():
        print(f"\n>>> 解析成功！预览前 5 行:")
        with open(output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print("".join(lines[:5]).strip())
            if len(lines) > 5:
                print("  ...")