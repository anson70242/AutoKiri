# src/agents/baseAgent.py
import json
import requests
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseAgent(ABC):
    """
    所有 Ollama Agent 的基础逻辑类。
    支持基础请求、强制 JSON 输出，以及通用的 Map-Reduce 任务流程。
    """
    def __init__(self, host: str = "http://localhost:11434", model: str = "qwen3:14b", timeout: int = 300, options: dict = None):
        # 移除结尾可能的斜杠，确保拼接正确
        self.host = host.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.options = options or {}  # 接收从 config 传来的 options
        self.api_url = f"{self.host}/api/chat"

    def check_connection(self) -> bool:
        """检查 Ollama 服务是否已启动且模型就绪"""
        try:
            res = requests.get(f"{self.host}/api/tags", timeout=5)
            if res.status_code == 200:
                # 可以进一步检查 self.model 是否存在于列表中
                return True
            return False
        except requests.RequestException:
            return False

    def chat(self, messages: List[Dict[str, str]], temperature: float = None, json_format: bool = False) -> str:
        """
        调用 Ollama Chat API 的基础方法
        :param messages: 对话历史 [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        :param temperature: 温度，预设覆盖 config 的对应设置；若都不传，则默认 0.3
        :param json_format: 是否要求 LLM 强制返回 JSON 对象
        """
        # 复制实例化的配置，避免修改到原有的字典
        chat_options = self.options.copy()
        
        # 如果方法被单独传入了 temperature，则覆盖 options 里的设置 (如 map_reduce 指定的 0.1)
        if temperature is not None:
            chat_options["temperature"] = temperature

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": chat_options
        }
        
        # Ollama 支持设定 format: "json" 强制限定输出结构
        if json_format:
            payload["format"] = "json"

        try:
            response = requests.post(self.api_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json().get('message', {}).get('content', '')
        except requests.exceptions.RequestException as e:
            print(f"[Agent Error] 请求 LLM 失败 ({self.model}): {e}")
            return ""

    def map_reduce(self, payloads: List[str], system_prompt: str, is_json_output: bool = True) -> List[Any]:
        """
        通用的 Map-Reduce 流程调度方法。
        
        【Map 阶段】: 针对每一个被切割的 Payload 发送给 LLM 处理。
        【Reduce 阶段】: 将处理结果汇总到一个 List 阵列中回传，交由调用方（如 chunker）进行处理。
        """
        map_results = []
        total = len(payloads)
        
        print(f"\n[Agent] 开始 LLM Map 阶段，共计 {total} 个区块...")
        for i, payload in enumerate(payloads):
            print(f"  - 正在处理区块 [{i+1}/{total}] ...")
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": payload}
            ]
            
            # 向 LLM 拿取结果 (这里的 0.1 会覆盖掉实例化时 config 传入的温度)
            res_text = self.chat(messages, json_format=is_json_output)

            print(f"      [Debug] LLM 返回截取: {res_text[:150]}...")
            
            if is_json_output:
                try:
                    # 尝试将返回的字符串解析为 Dict / List
                    parsed_res = json.loads(res_text)
                    map_results.append(parsed_res)
                except json.JSONDecodeError:
                    print(f"[Agent Warning] 区块 {i+1} 返回的结果无法解析为 JSON: {res_text[:50]}...")
                    # 如果解析失败，塞入一个空列表或保留原始文字，以避免影响后续 Merge
                    map_results.append([])
            else:
                map_results.append(res_text)
                
        print("[Agent] Map 处理完成。")
        return map_results

    @abstractmethod
    def process(self, *args, **kwargs):
        """子类（如 TranslateAgent, HighlightAgent）必须实现具体的调用组装逻辑"""
        pass