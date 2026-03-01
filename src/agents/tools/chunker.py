# src/agents/tools/chunker.py
import re
import json
from pathlib import Path
from typing import List, Dict, Any

class SrtChunker:
    """
    负责将 SRT 档切割（Chunking），提取给 LLM，并在最后根据时间轴进行还原（Merge）。
    """
    def __init__(self, chunk_size: int = 50, overlap: int = 5):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def parse_srt(self, filepath: str | Path) -> List[Dict[str, Any]]:
        """将 SRT 档案解析为内存对象，保留行号和时间"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 根据双换行符分割字幕块
        blocks = re.split(r'\n\s*\n', content.strip())
        parsed_blocks = []

        for block in blocks:
            lines = block.split('\n')
            if len(lines) >= 3:
                idx = lines[0].strip()
                times = lines[1].split(' --> ')
                if len(times) == 2:
                    text = '\n'.join(lines[2:]).strip()
                    parsed_blocks.append({
                        'id': int(idx) if idx.isdigit() else idx,
                        'start': times[0].strip(),
                        'end': times[1].strip(),
                        'text': text
                    })
        return parsed_blocks

    def get_llm_payloads(self, parsed_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Map 阶段的准备：
        chunk_size 决定核心句数，overlap 决定前后各自扩展的上下文句数。
        将其转换为仅包含 ID 和 Text 的 JSON 字符串，缩短 LLM 上下文。
        """
        chunks = []
        step = self.chunk_size
        total_blocks = len(parsed_blocks)

        if step <= 0:
            raise ValueError("chunk_size 必须大于 0")

        for i in range(0, total_blocks, step):
            # 计算包含前后 overlap 的实际起止索引
            start_idx = max(0, i - self.overlap)
            end_idx = min(total_blocks, i + self.chunk_size + self.overlap)
            
            chunk_blocks = parsed_blocks[start_idx : end_idx]
            
            # 只提取行号和文本（过滤掉 start/end 时间轴）
            llm_payload = [{"id": b["id"], "text": b["text"]} for b in chunk_blocks]
            
            chunks.append({
                "chunk_index": i // step,
                "start_id": chunk_blocks[0]["id"], # 注意：此时的首尾 ID 是包含了 overlap 的
                "end_id": chunk_blocks[-1]["id"],
                "payload_str": json.dumps(llm_payload, ensure_ascii=False)
            })
            
        return chunks

    def merge_and_export(self, llm_processed_chunks: List[Any], original_blocks: List[Dict[str, Any]], output_path: str | Path):
        """
        Reduce 阶段：
        将 LLM 返回的 List[JSON] 结果合并，并映射回原有的时间轴对象上，最后生成新的 SRT。
        """
        text_map = {}
        for payload in llm_processed_chunks:
            # 应对 LLM 擅自增加外层 Dict 的情况，例如 {"data": [{"id": 1...}]}
            if isinstance(payload, dict):
                # 寻找字典里真正装载数据的 list
                for key, val in payload.items():
                    if isinstance(val, list):
                        payload = val
                        break
                else:
                    # 如果找不到 list，可能 LLM 只返回了单条对象的 dict，把它包成 list
                    payload = [payload]

            # 确保现在 payload 是一个列表
            if isinstance(payload, list):
                for item in payload:
                    # 确保 item 是字典且包含需要的 key
                    if isinstance(item, dict) and 'id' in item and 'text' in item:
                        text_map[str(item['id'])] = str(item['text'])

        # 开始重建 SRT 档案
        with open(output_path, 'w', encoding='utf-8') as f:
            for block in original_blocks:
                b_id = str(block['id'])
                start = block['start']
                end = block['end']
                
                # 若对应行号有处理结果，则用结果替换；否则保留原本文本
                out_text = text_map.get(b_id, block['text'])
                
                f.write(f"{b_id}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{out_text}\n\n")