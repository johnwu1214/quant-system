#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 策略自动生成模块
基于 MiniMax 大模型自动生成量化交易策略
"""
import os
import sys
import json
import random
from datetime import datetime
from typing import List, Dict, Optional

try:
    from openai import OpenAI
    MINIMAX_AVAILABLE = True
except ImportError:
    MINIMAX_AVAILABLE = False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class AIStrategyGenerator:
    """AI 策略生成器"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.client = None
        if self.api_key and MINIMAX_AVAILABLE:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.minimaxi.com/v1"
            )
        
        # 策略模板库
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict:
        """加载策略模板"""
        return {
            "trend_following": {
                "name": "趋势跟踪策略",
                "description": "基于均线/趋势线进行趋势交易",
                "signals": ["MA金叉", "MA多头排列", "突破新高"],
                "positions": ["突破买入", "回踩买入", "趋势回调买入"]
            },
            "mean_reversion": {
                "name": "均值回归策略",
                "description": "价格偏离均值后回归",
                "signals": ["RSI超卖", "价格偏离MA", "布林带下轨"],
                "positions": ["超卖买入", "偏离买入"]
            },
            "momentum": {
                "name": "动量策略",
                "description": "追涨杀跌，顺势而为",
                "signals": ["MACD金叉", "动量 positive", "成交量放大"],
                "positions": ["追涨买入", "动量增强买入"]
            },
            "breakout": {
                "name": "突破策略",
                "description": "突破关键价位后买入",
                "signals": ["突破20日高点", "突破平台", "放量突破"],
                "positions": ["突破买入", "回踩确认买入"]
            },
            "value": {
                "name": "价值策略",
                "description": "低估值买入",
                "signals": ["PE低于均值", "PB低估", "股息率高"],
                "positions": ["低估买入", "分批建仓"]
            },
            "grid": {
                "name": "网格策略",
                "description": "震荡行情中高卖低买",
                "signals": ["价格触及网格", "波动率稳定"],
                "positions": ["网格买入", "网格卖出"]
            }
        }
    
    def generate_strategy(self, market_condition: str, risk_level: str = "medium") -> Dict:
        """生成策略"""
        if not self.client:
            return self._generate_fallback_strategy(market_condition, risk_level)
        
        prompt = f"""
请生成一个量化交易策略。

市场环境: {market_condition}
风险偏好: {risk_level}

请返回JSON格式的策略配置：
{{
    "name": "策略名称",
    "type": "趋势跟踪/均值回归/动量/突破/价值/网格",
    "description": "策略描述",
    "entry_conditions": ["条件1", "条件2"],
    "exit_conditions": ["条件1", "条件2"],
    "position_size": "仓位管理方式",
    "stop_loss": "止损方式",
    "take_profit": "止盈方式",
    "timeframe": "时间周期",
    "parameters": {{"参数名": "默认值"}}
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model="abab6.5s-chat",
                messages=[
                    {"role": "system", "content": "你是一位资深的量化交易策略专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            strategy = json.loads(content)
            return strategy
            
        except Exception as e:
            print(f"⚠️ AI生成失败: {e}")
            return self._generate_fallback_strategy(market_condition, risk_level)
    
    def _generate_fallback_strategy(self, market_condition: str, risk_level: str) -> Dict:
        """备用策略生成"""
        templates = list(self.templates.values())
        
        if "震荡" in market_condition or "整理" in market_condition:
            selected = self.templates["grid"]
        elif "上涨" in market_condition or "牛市" in market_condition:
            selected = self.templates["trend_following"]
        elif "下跌" in market_condition or "熊市" in market_condition:
            selected = self.templates["mean_reversion"]
        else:
            selected = random.choice(templates)
        
        strategy = {
            "name": f"AI-{selected['name']}",
            "type": list(self.templates.keys())[list(self.templates.values()).index(selected)],
            "description": f"基于 {selected['description']}，适应{market_condition}环境",
            "entry_conditions": selected["signals"][:2],
            "exit_conditions": [
                "RSI超买",
                "MACD死叉",
                "达到止盈位"
            ],
            "position_size": "10%-30%",
            "stop_loss": "-5%" if risk_level == "low" else "-8%" if risk_level == "medium" else "-10%",
            "take_profit": "+10%" if risk_level == "low" else "+15%" if risk_level == "medium" else "+20%",
            "timeframe": "1d",
            "parameters": {
                "ma_short": 5,
                "ma_long": 20,
                "rsi_period": 14,
                "rsi_oversold": 30,
                "rsi_overbought": 70
            },
            "ai_generated": False
        }
        
        return strategy
    
    def optimize_parameters(self, strategy: Dict, market_data: List) -> Dict:
        """优化策略参数"""
        # 简化的参数优化（实际需要回测）
        optimized = strategy.copy()
        optimized["parameters"] = {
            "ma_short": 5,
            "ma_long": 20,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70
        }
        optimized["optimized"] = True
        return optimized
    
    def combine_strategies(self, strategies: List[Dict]) -> Dict:
        """组合多个策略"""
        return {
            "name": "组合策略",
            "type": "composite",
            "components": [s.get("name", "策略") for s in strategies],
            "weight": [1.0 / len(strategies)] * len(strategies),
            "rebalance": "weekly",
            "description": f"由{len(strategies)}个子策略组成"
        }


class StrategyLibrary:
    """策略库管理"""
    
    def __init__(self):
        self.strategies = {}
        self.load_default_strategies()
    
    def load_default_strategies(self):
        """加载默认策略"""
        default_strategies = [
            {
                "name": "均线多头排列",
                "type": "trend_following",
                "entry": "ma5 > ma10 > ma20",
                "exit": "ma5 < ma10"
            },
            {
                "name": "RSI超卖反弹",
                "type": "mean_reversion",
                "entry": "rsi(14) < 30",
                "exit": "rsi(14) > 70"
            },
            {
                "name": "MACD金叉",
                "type": "momentum",
                "entry": "macd > signal",
                "exit": "macd < signal"
            },
            {
                "name": "布林带突破",
                "type": "breakout",
                "entry": "close > upper_band",
                "exit": "close < lower_band"
            }
        ]
        
        for s in default_strategies:
            self.strategies[s["name"]] = s
    
    def add_strategy(self, strategy: Dict):
        """添加策略"""
        name = strategy.get("name", "未命名策略")
        self.strategies[name] = strategy
    
    def get_strategy(self, name: str) -> Optional[Dict]:
        """获取策略"""
        return self.strategies.get(name)
    
    def list_strategies(self) -> List[str]:
        """列出所有策略"""
        return list(self.strategies.keys())


# 测试
if __name__ == "__main__":
    generator = AIStrategyGenerator()
    
    print("🧪 测试 AI 策略生成...")
    
    # 测试不同市场环境
    conditions = ["震荡上行", "强势上涨", "下跌调整"]
    
    for cond in conditions:
        strategy = generator.generate_strategy(cond, risk_level="medium")
        print(f"\n📈 市场环境: {cond}")
        print(f"   策略: {strategy.get('name')}")
        print(f"   类型: {strategy.get('type')}")
        print(f"   入场: {strategy.get('entry_conditions')}")
        print(f"   止损: {strategy.get('stop_loss')}")
    
    print("\n✅ AI 策略生成模块测试完成")
