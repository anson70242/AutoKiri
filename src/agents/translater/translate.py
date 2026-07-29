# src/agents/translater/translate.py
"""
LLM 字幕翻译器。

设计要点（保证时间轴绝不错位）：
    1. 时间轴 (start/end) 全程只保存在 Python 内存里，LLM 只看到 {id, text}。
    2. LLM 返回 id -> text，靠 SrtChunker.merge_and_export 贴回原始时间轴。
    3. 缺失的 id 自动回退成原文，绝不会出现「行消失、后面整体串位」。
    4. chunk 之间用 overlap 提供上下文，但 merge 时只采用每个 chunk 的
       核心区间 (core_ids)，丢弃 overlap 部分较敷衍的译文。

只依赖 requests（走 OpenAI 兼容的 /chat/completions 端点），无需安装 openai。
"""
import os
import sys
import re
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
from dotenv import load_dotenv

from src.agents.tools.chunker import SrtChunker


def _resolve_project_root() -> Path:
    """兼容源码运行与 PyInstaller 打包：冻结态取 exe 所在目录，否则取仓库根目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


# 加载项目根目录的 .env（LLM 端点 / API Key 存放于此，不写入代码）
_PROJECT_ROOT = _resolve_project_root()
load_dotenv(_PROJECT_ROOT / ".env")

# ------------------------------------------------------------------ #
#  默认 LLM 连接参数
#  端点与密钥统一从 .env 读取（AUTOKIRI_LLM_BASE_URL / AUTOKIRI_LLM_API_KEY）
#  代码里不再硬编码密钥；仅模型名保留一个可覆盖的默认值。
# ------------------------------------------------------------------ #
DEFAULT_BASE_URL = ""
DEFAULT_API_KEY = ""
DEFAULT_MODEL = "unsloth/Qwen3.6-27B-GGUF:UD-Q4_K_XL"

# Prompt / 词表 默认路径（相对本文件定位到 src/agents/prompts/）
_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
DEFAULT_PROMPT_PATH = _PROMPT_DIR / "translater.md"
DEFAULT_GLOSSARY_PATH = _PROMPT_DIR / "vocab.md"


class SrtTranslator:
    def __init__(
        self,
        prompt_path: Path = DEFAULT_PROMPT_PATH,
        glossary_path: Optional[Path] = DEFAULT_GLOSSARY_PATH,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str = DEFAULT_API_KEY,
        model: str = DEFAULT_MODEL,
        chunk_size: int = 50,
        overlap: int = 5,
        temperature: float = 0.3,
        timeout: int = 300,
        max_retries: int = 2,
    ):
        # .env / 环境变量优先（端点与密钥统一存放在 .env，不落到代码/仓库）
        self.base_url = (os.getenv("AUTOKIRI_LLM_BASE_URL") or base_url).rstrip("/")
        self.api_key = os.getenv("AUTOKIRI_LLM_API_KEY") or api_key
        self.model = os.getenv("AUTOKIRI_LLM_MODEL") or model

        if not self.base_url:
            raise ValueError(
                "未配置 LLM 端点，请在项目根目录 .env 中设置 AUTOKIRI_LLM_BASE_URL"
            )
        if not self.api_key:
            print("[Warning] 未在 .env 中找到 AUTOKIRI_LLM_API_KEY，将以空密钥请求（若端点需要鉴权会失败）。")

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries

        self.system_prompt = self._build_system_prompt(prompt_path, glossary_path)

    # ---------------------------------------------------------------- #
    #  1. 读取 prompt + 词表，拼成 system prompt
    # ---------------------------------------------------------------- #
    @staticmethod
    def _build_system_prompt(prompt_path: Path, glossary_path: Optional[Path]) -> str:
        prompt_path = Path(prompt_path)
        if not prompt_path.exists():
            raise FileNotFoundError(f"找不到翻译 Prompt 文件: {prompt_path}")
        text = prompt_path.read_text(encoding="utf-8")

        if glossary_path:
            glossary_path = Path(glossary_path)
            if glossary_path.exists():
                glossary = glossary_path.read_text(encoding="utf-8")
                text += (
                    "\n\n---\n\n"
                    "### 【强制】翻译时必须应用的权威词表\n"
                    "以下词表优先级高于正文中的参考术语表，遇到即按此翻译：\n\n"
                    f"{glossary}"
                )
            else:
                print(f"[Warning] 找不到词表文件，将不带词表翻译: {glossary_path}")

        return text

    # ---------------------------------------------------------------- #
    #  2. 调 LLM（带重试）
    # ---------------------------------------------------------------- #
    def _call_llm(self, payload_str: str) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": payload_str},
            ],
            "temperature": self.temperature,
            "stream": False,
        }

        last_err = None
        for attempt in range(1, self.max_retries + 2):  # 首次 + max_retries 次重试
            try:
                resp = requests.post(url, headers=headers, json=body, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                last_err = e
                print(f"[Warning] LLM 请求失败 (第 {attempt} 次): {e}")
                if attempt <= self.max_retries:
                    time.sleep(2 * attempt)
        raise RuntimeError(f"LLM 请求在重试 {self.max_retries} 次后仍失败: {last_err}")

    # ---------------------------------------------------------------- #
    #  3. 解析 LLM 返回的 JSON（容错：去 think 块 / 代码围栏 / 截取数组）
    # ---------------------------------------------------------------- #
    @staticmethod
    def _parse_json_array(raw: str) -> List[Dict[str, Any]]:
        if not raw:
            return []
        text = raw.strip()

        # Qwen3 等模型可能吐 <think>...</think>，先剥掉
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        # 去掉 ```json ... ``` 代码围栏
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # 兜底：截取第一个 '[' 到最后一个 ']'
            start, end = text.find("["), text.rfind("]")
            if start != -1 and end != -1 and end > start:
                try:
                    parsed = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    print("[Warning] 无法解析该 chunk 的 LLM 输出，将回退为原文。")
                    return []
            else:
                print("[Warning] LLM 输出中找不到 JSON 数组，将回退为原文。")
                return []

        # 兼容 LLM 擅自套了一层 {"data": [...]}
        if isinstance(parsed, dict):
            for val in parsed.values():
                if isinstance(val, list):
                    parsed = val
                    break
            else:
                parsed = [parsed]

        return parsed if isinstance(parsed, list) else []

    # ---------------------------------------------------------------- #
    #  4. 主流程
    # ---------------------------------------------------------------- #
    def translate(self, srt_path: Path, output_path: Optional[Path] = None) -> Optional[Path]:
        srt_path = Path(srt_path)
        if not srt_path.exists():
            print(f"[Error] 找不到待翻译的 SRT: {srt_path}")
            return None

        if output_path is None:
            output_path = srt_path.with_name(f"{srt_path.stem}.zh.srt")
        output_path = Path(output_path)

        chunker = SrtChunker(chunk_size=self.chunk_size, overlap=self.overlap)

        original_blocks = chunker.parse_srt(srt_path)
        if not original_blocks:
            print(f"[Warning] SRT 解析为空，跳过翻译: {srt_path.name}")
            return None

        payloads = chunker.get_llm_payloads(original_blocks)
        total = len(payloads)
        print(f"[Info] 🌐 开始翻译 {srt_path.name} —— 共 {len(original_blocks)} 句 / {total} 个 chunk")

        processed_chunks: List[List[Dict[str, Any]]] = []
        for chunk in payloads:
            idx = chunk["chunk_index"]
            print(f"[Info]   翻译 chunk {idx + 1}/{total} (id {chunk['start_id']}~{chunk['end_id']}) ...")

            raw = self._call_llm(chunk["payload_str"])
            parsed = self._parse_json_array(raw)

            # 只保留本 chunk 的核心区间，丢弃 overlap 部分（避免重复/敷衍译文覆盖）
            core_ids = {str(cid) for cid in chunk["core_ids"]}
            filtered = [
                item
                for item in parsed
                if isinstance(item, dict) and "id" in item and str(item["id"]) in core_ids
            ]
            processed_chunks.append(filtered)

        # merge_and_export 会遍历 original_blocks，缺失的 id 自动回退原文 -> 时间轴永不错位
        chunker.merge_and_export(processed_chunks, original_blocks, output_path)
        print(f"[Success] ✅ 翻译完成: {output_path.name}")
        return output_path

    # ---------------------------------------------------------------- #
    #  便捷工厂：从 ConfigManager 读取覆盖参数（可选）
    # ---------------------------------------------------------------- #
    @classmethod
    def from_config(cls, config) -> "SrtTranslator":
        """
        从 ConfigManager 读取 translater 相关配置（若不存在则用默认值）。
        config.yaml 期望结构（全部可选）：
            agents:
              - translater:
                  base_url: "..."
                  api_key: "..."
                  model: "..."
                  chunk_size: 50
                  overlap: 5
        """
        cfg = {}
        try:
            cfg = config.get_agent_config("translater") or {}
        except Exception:
            pass

        prompt_path = config.get_prompt_path("translater") or DEFAULT_PROMPT_PATH
        glossary_path = config.get_prompt_path("translater_glossary") or DEFAULT_GLOSSARY_PATH

        return cls(
            prompt_path=prompt_path,
            glossary_path=glossary_path,
            base_url=cfg.get("base_url", DEFAULT_BASE_URL),
            api_key=cfg.get("api_key", DEFAULT_API_KEY),
            model=cfg.get("model", DEFAULT_MODEL),
            chunk_size=cfg.get("chunk_size", 50),
            overlap=cfg.get("overlap", 5),
        )


# ------------------------------------------------------------------ #
#  CLI: python -m src.agents.translater.translate <input.srt> [output.srt]
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python -m src.agents.translater.translate <input.srt> [output.srt]")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else None

    SrtTranslator().translate(in_path, out_path)
