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

    def merge_and_export(self, llm_processed_chunks: List[List[Dict[str, Any]]], original_blocks: List[Dict[str, Any]], output_path: str | Path):
        """
        Reduce 阶段：
        将 LLM 返回的 List[JSON] 结果合并，并映射回原有的时间轴对象上，最后生成新的 SRT。
        """
        text_map = {}
        # 遍历所有 chunk 的结果
        for payload in llm_processed_chunks:
            # 假设 LLM 返回的数据是 [{"id": 1, "text": "处理后的文字"}, ...]
            for item in payload:
                if 'id' in item and 'text' in item:
                    # 使用字典来去重/覆盖 Overlap 区域（后面的 chunk 覆盖前面的）
                    text_map[str(item['id'])] = str(item['text'])

        # 开始重建 SRT 档案
        with open(output_path, 'w', encoding='utf-8') as f:
            for block in original_blocks:
                b_id = str(block['id'])
                start = block['start']
                end = block['end']
                
                # 若对应行号有处理结果，则用结果替换；否则保留原本文本（容错机制）
                out_text = text_map.get(b_id, block['text'])
                
                f.write(f"{b_id}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{out_text}\n\n")

# test_chunker.py
import json
from pathlib import Path
from src.agents.tools.chunker import SrtChunker

def create_dummy_srt(filepath: Path):
    """生成一个测试用的假 SRT 文件"""
    content = """1
00:00:01,000 --> 00:00:02,000
这是第一句台词。

2
00:00:03,000 --> 00:00:04,000
这是第二句台词，准备被切割。

3
00:00:05,000 --> 00:00:06,000
第三句话，是第一个 chunk 的核心结尾。

4
00:00:07,000 --> 00:00:08,000
第四句话用来测试 overlap，它是首个 chunk 的尾巴。

5
00:00:09,000 --> 00:00:10,000
第五句话，位于第二个 chunk 的绝对核心。

6
00:00:11,000 --> 00:00:12,000
第六句话，继续稳坐核心区域。

7
00:00:13,000 --> 00:00:14,000
第七句话，充当第二个 chunk 的后置 overlap。

8
00:00:15,000 --> 00:00:16,000
第八句话，正式进入第三个 chunk。

9
00:00:17,000 --> 00:00:18,000
第九句话，快要结束了。

10
00:00:19,000 --> 00:00:20,000
第十句话，完美的收尾，测试彻底结束。
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n\n")

def main():
    print("=" * 40)
    print("   🚀 开始测试 SrtChunker")
    print("=" * 40)
    
    test_input = Path("test_input.srt")
    test_output = Path("test_output.srt")
    
    # 1. 建立测试数据
    create_dummy_srt(test_input)
    print(f"✅ [1/5] 已生成测试 SRT: {test_input.name}")
    
    # 2. 实例化 Chunker (设定 chunk_size=3, overlap=1 方便观察)
    chunker = SrtChunker(chunk_size=3, overlap=1)
    
    # 3. 解析原始 SRT
    original_blocks = chunker.parse_srt(test_input)
    print(f"✅ [2/5] 成功解析 SRT，共提取 {len(original_blocks)} 行纯文本格式。")
    
    # 4. 获取 LLM Map 阶段需要的 Payload
    chunks = chunker.get_llm_payloads(original_blocks)
    print(f"✅ [3/5] 切片完成，共分为 {len(chunks)} 个 Chunk：\n")
    
    # 5. 模拟 LLM 处理过程 (为每一句加上 "[模拟翻译]" 字样)
    llm_processed_results = []
    
    for i, chunk in enumerate(chunks):
        print(f"   📦 [Chunk {i}] ID范围: {chunk['start_id']} -> {chunk['end_id']}")
        print(f"      发给 LLM 的 JSON 字符串:\n      {chunk['payload_str']}")
        
        # 假装这是 LLM 收到了 JSON 并解析
        llm_input = json.loads(chunk['payload_str'])
        
        # 假装 LLM 处理后返回了全新的 JSON 列表
        llm_output = []
        for item in llm_input:
            llm_output.append({
                "id": item["id"],
                "text": item["text"] + " [✅已由LLM模拟翻译]"
            })
            
        llm_processed_results.append(llm_output)
        print("-" * 30)
        
    # 6. 将 LLM 处理结果 Merge 回时间轴并导出
    chunker.merge_and_export(llm_processed_results, original_blocks, test_output)
    print(f"✅ [4/5] 还原时间轴并合并成功！档案输出至: {test_output.name}")
    
    # 7. 打印验证
    print("\n✅ [5/5] 最终输出的 SRT 内容预览:")
    print("=" * 40)
    with open(test_output, "r", encoding="utf-8") as f:
        print(f.read().strip())
    print("=" * 40)
    
    # 阅后即焚（可选，若想保留档案查看可注释掉这两行）
    # test_input.unlink(missing_ok=True)
    # test_output.unlink(missing_ok=True)
    # print("🧹 测试用临时文件已清理。")

if __name__ == "__main__":
    main()