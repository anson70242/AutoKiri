# to_chinese.py
"""
独立字幕翻译脚本：把日文 SRT 翻译成中文 SRT。

用法：
    python .\\to_chinese.py <日文.srt> [输出.srt]      # 指定文件
    python .\\to_chinese.py                             # 交互式输入路径

时间轴由 Python 全程保管，LLM 只翻译文本，绝不会错位。
配置读取自 config.yaml 的 agents.translater（不存在则用内置默认值 / 环境变量）。
"""
import os
import sys
import traceback
from pathlib import Path

from src.core import get_base_path, ConfigManager
from src.agents.translater import SrtTranslator


def main():
    print("=" * 60 + "\n       AutoKiri-Flow [字幕翻译 · 日→中]       \n" + "=" * 60)

    # 1. 解析输入路径（命令行参数优先，否则交互式询问）
    if len(sys.argv) >= 2:
        in_path = Path(sys.argv[1].strip().strip('"'))
    else:
        raw = input("\n 请输入日文 SRT 文件路径: ").strip().strip('"')
        in_path = Path(raw)

    out_path = Path(sys.argv[2].strip().strip('"')) if len(sys.argv) >= 3 else None

    if not in_path.exists():
        print(f"[Error] 找不到输入文件: {in_path}")
        return
    if in_path.suffix.lower() != ".srt":
        print(f"[Warning] 输入文件后缀不是 .srt，仍将尝试解析: {in_path.name}")

    # 2. 从 config 构建翻译器（读不到就用默认值）
    config = ConfigManager(get_base_path())
    translator = SrtTranslator.from_config(config)

    print(f"[Info] 模型: {translator.model}")
    print(f"[Info] 端点: {translator.base_url}")

    # 3. 翻译
    result = translator.translate(in_path, out_path)
    if result:
        print(f"\n[Done] 中文字幕已保存: {result}")
    else:
        print("\n[Failed] 翻译未能完成，请检查上面的错误信息。")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("\n" + "!" * 60)
        print("❌ [致命错误] 翻译过程中发生崩溃：")
        traceback.print_exc()
        print("!" * 60)
    finally:
        print("\n")
        os.system("pause")
