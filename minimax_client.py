#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax API 客户端模块 - 支持 Token Plan
支持文本生成、嵌入向量等功能
文档: https://api.minimax.chat/
"""
import json
import requests
import os
from typing import Optional, List, Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# 默认模型
DEFAULT_CHAT_MODEL = "abab6.5s-chat"  # MiniMax 最新对话模型
DEFAULT_EMBEDDING_MODEL = "embo-01"   # MiniMax 嵌入模型


class MiniMaxClient:
    """MiniMax API 客户端 - 支持 Token Plan"""
    
    def __init__(self, api_key: Optional[str] = None, group_id: Optional[str] = None):
        """
        初始化 MiniMax 客户端
        
        Args:
            api_key: MiniMax API Key，如果不提供则从配置文件读取
            group_id: MiniMax Group ID，如果不提供则从配置文件读取
        """
        config = self._load_config()
        
        self.api_key = api_key or config.get("minimax_api_key", "")
        self.group_id = group_id or config.get("minimax_group_id", "")
        self.base_url = config.get("minimax_base_url", "https://api.minimax.chat/v1")
        
        if not self.api_key:
            raise ValueError("MiniMax API Key 未配置，请在 config.json 中设置 minimax_api_key")
        if not self.group_id:
            raise ValueError("MiniMax Group ID 未配置，请在 config.json 中设置 minimax_group_id")
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return {}
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = DEFAULT_CHAT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        对话补全
        
        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            model: 模型名称
            temperature: 温度参数 (0-1)
            max_tokens: 最大生成token数
            stream: 是否流式输出
        
        Returns:
            API 响应结果
        """
        # Token Plan 需要在 URL 中携带 GroupId
        url = f"{self.base_url}/text/chatcompletion_v2?GroupId={self.group_id}"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"请求失败: {str(e)}"}
    
    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = DEFAULT_CHAT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """
        简化版文本生成
        
        Args:
            prompt: 用户输入
            system_prompt: 系统提示词
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大生成token数
        
        Returns:
            生成的文本内容
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        result = self.chat_completion(messages, model, temperature, max_tokens)
        
        if "error" in result:
            return f"错误: {result['error']}"
        
        # 检查是否有错误码
        if "base_resp" in result and result["base_resp"].get("status_code") != 0:
            return f"API错误: {result['base_resp'].get('status_msg', '未知错误')}"
        
        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            return f"解析响应失败: {e}, 响应: {result}"
    
    def get_embedding(
        self,
        texts: List[str],
        model: str = DEFAULT_EMBEDDING_MODEL,
        type: str = "db"  # "db" 用于数据库存储，"query" 用于查询
    ) -> Dict[str, Any]:
        """
        获取文本嵌入向量
        
        Args:
            texts: 文本列表
            model: 嵌入模型
            type: 嵌入类型 ("db" 或 "query")
        
        Returns:
            嵌入向量结果
        """
        url = f"{self.base_url}/embeddings?GroupId={self.group_id}"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "input": texts,
            "type": type
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"请求失败: {str(e)}"}
    
    def analyze_stock_sentiment(self, stock_name: str, news_text: str) -> Dict[str, Any]:
        """
        分析股票新闻情绪 (示例功能)
        
        Args:
            stock_name: 股票名称
            news_text: 新闻文本
        
        Returns:
            情绪分析结果
        """
        system_prompt = """你是一位专业的金融分析师，擅长分析股票新闻的情绪倾向。
请分析给定新闻对指定股票的影响，输出JSON格式：
{
    "sentiment": "positive/negative/neutral",
    "confidence": 0-1之间的数值,
    "impact_level": "high/medium/low",
    "summary": "简要分析",
    "key_points": ["要点1", "要点2"]
}"""
        
        prompt = f"""请分析以下关于【{stock_name}】的新闻：

{news_text}

请严格按照系统提示的JSON格式输出。"""
        
        response = self.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1000
        )
        
        try:
            # 尝试解析JSON
            import json
            return json.loads(response)
        except:
            return {
                "sentiment": "unknown",
                "confidence": 0,
                "raw_response": response
            }


def test_minimax():
    """测试 MiniMax 连接"""
    try:
        client = MiniMaxClient()
        print("✅ MiniMax 客户端初始化成功")
        
        # 测试简单对话
        response = client.generate_text(
            prompt="你好，请简单介绍一下自己",
            temperature=0.7
        )
        print(f"\n测试响应:\n{response[:200]}...")
        return True
    except Exception as e:
        print(f"❌ MiniMax 测试失败: {e}")
        return False


if __name__ == "__main__":
    test_minimax()
