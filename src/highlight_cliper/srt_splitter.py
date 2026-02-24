# src/highlight_cliper/srt_splitter.py
import math
import re
import shutil
from pathlib import Path
from typing import List

class SrtSplitter:
    """负责将过长的 SRT 档案等分切割，并复制相关的 Prompt 文件到目标资料夹"""
    
    def __init__(self, max_blocks: int = 800):
        self.max_blocks = max_blocks

    def split_srt(self, srt_path: Path) -> List[Path]:
        """将 SRT 以块为单位进行读取，计算等分并切片"""
        if not srt_path or not srt_path.exists():
            return []

        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            
        if not content:
            print("[Warning] SRT 文件为空，跳过切割。")
            return []
            
        # 使用正则匹配空行来分割每一个字幕块 (支援 Windows/Linux 换行符)
        blocks = re.split(r'\r?\n[ \t]*\r?\n', content)
        total_blocks = len(blocks)
        
        # 计算要切成几份，以及每份多少块 (确保尽量均分)
        # 比如 801 块 -> 切成 2 份 -> 每份 ceil(801/2) = 401 块 (而不是 800 和 1)
        num_chunks = math.ceil(total_blocks / self.max_blocks)
        if num_chunks == 0:
            return []
            
        blocks_per_chunk = math.ceil(total_blocks / num_chunks)
        
        output_dir = srt_path.parent
        base_name = srt_path.stem
        split_files = []
        
        for i in range(num_chunks):
            start_idx = i * blocks_per_chunk
            end_idx = min((i + 1) * blocks_per_chunk, total_blocks)
            chunk_blocks = blocks[start_idx:end_idx]
            
            # 顺手重新编号 (对 LLM 解析更友好，让每份 SRT 都从 1 开始)
            renumbered_blocks = []
            for idx, block in enumerate(chunk_blocks, start=1):
                # 把第一行的原数字替换为新的数字
                lines = block.split('\n', 1)
                if len(lines) == 2:
                    renumbered_blocks.append(f"{idx}\n{lines[1]}")
                else:
                    renumbered_blocks.append(block)
            
            chunk_path = output_dir / f"{base_name}_part{i+1}.srt"
            with open(chunk_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(renumbered_blocks) + "\n\n")
                
            split_files.append(chunk_path)
            print(f"[Info] 成功产生字幕片段: {chunk_path.name} (含 {len(chunk_blocks)} 句对话)")
            
        return split_files

    def copy_prompts(self, target_dir: Path, prompt_paths: List[Path]):
        """将指定的 Markdown Prompt 档案复制到目标资料夹"""
        for p in prompt_paths:
            if p and p.exists():
                dest = target_dir / p.name
                shutil.copy2(p, dest)
                print(f"[Info] 已部署 Prompt 备忘文件: {dest.name}")
            else:
                print(f"[Warning] 找不到 Prompt 文件: {p}")