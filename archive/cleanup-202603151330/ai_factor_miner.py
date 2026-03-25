#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 因子挖掘模块
基于 MiniMax 大模型自动生成和评估量化因子
"""
import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Optional

# 尝试导入 MiniMax SDK
try:
    from openai import OpenAI
    MINIMAX_AVAILABLE = True
except ImportError:
    MINIMAX_AVAILABLE = False

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class AIFactorMiner:
    """AI 因子挖掘器"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.client = None
        if self.api_key and MINIMAX_AVAILABLE:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.minimaxi.com/v1"
            )
    
    def generate_factors(self, market_data: Dict, count: int = 5) -> List[Dict]:
        """基于市场数据生成因子"""
        if not self.client:
            return self._generate_fallback_factors(count)
        
        prompt = f"""
你是一位量化投资专家。请根据以下市场数据特征，生成 {count} 个有效的量化因子。

市场数据特征：
- 价格范围: {market_data.get('price_range', 'N/A')}
- 波动率: {market_data.get('volatility', 'N/A')}
- 成交量: {market_data.get('volume', 'N/A')}
- 行业: {market_data.get('sector', 'N/A')}

要求：
1. 每个因子需要包含：名称、表达式、逻辑说明、预期效果
2. 因子应该是可计算的（基于OHLCV数据）
3. 兼顾技术面和基本面
4. 输出JSON数组格式

示例格式：
[{{"name": "MA5", "expression": "close_ma(5)", "logic": "5日均线", "effect": "趋势跟踪"}}]
"""
        
        try:
            response = self.client.chat.completions.create(
                model="abab6.5s-chat",
                messages=[
                    {"role": "system", "content": "你是一位资深的量化投资专家，擅长因子挖掘和策略开发。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            # 尝试解析JSON
            factors = json.loads(content)
            return factors
            
        except Exception as e:
            print(f"⚠️ AI生成失败: {e}")
            return self._generate_fallback_factors(count)
    
    def _generate_fallback_factors(self, count: int) -> List[Dict]:
        """备用因子库（当AI不可用时）"""
        fallback_factors = [
            {"name": "MA5_CROSS_MA20", "expression": "ma(5) > ma(20)", "logic": "5日均线上穿20日均线", "effect": "趋势反转"},
            {"name": "RSI_14", "expression": "rsi(14)", "logic": "14日RSI指标", "effect": "超买超卖"},
            {"name": "MACD_SIGNAL", "expression": "macd() - signal()", "logic": "MACD与信号线差值", "effect": "动量"},
            {"name": "BOLL_POSITION", "expression": "(close - lower) / (upper - lower)", "logic": "布林带位置", "effect": "波动"},
            {"name": "VOL_RATIO", "expression": "volume / volume_ma(20)", "logic": "成交量相对倍数", "effect": "成交量异常"},
            {"name": "HIGH_LOW_RATIO", "expression": "(high - low) / close", "logic": "日内振幅", "effect": "波动率"},
            {"name": "CLOSE_POSITION", "expression": "(close - open) / (high - low)", "logic": "收盘位置", "effect": "日内趋势"},
            {"name": "PE_RATIO", "expression": "close / eps", "logic": "市盈率", "effect": "估值"},
            {"name": "PB_RATIO", "expression": "close / book_value", "logic": "市净率", "effect": "估值"},
            {"name": "DIVIDEND_YIELD", "expression": "annual_dividend / close", "logic": "股息率", "effect": "收益"},
        ]
        return fallback_factors[:count]
    
    def evaluate_factor(self, factor: Dict, historical_data: List) -> Dict:
        """评估因子有效性"""
        # 计算 IC (Information Coefficient)
        # IR (Information Ratio)
        # 回测收益率
        
        return {
            "factor": factor.get("name"),
            "ic": 0.05,  # 模拟值
            "ir": 0.8,   # 模拟值
            "return": 0.12,  # 模拟值
            "win_rate": 0.55,
            "sharpe": 1.2,
            "valid": True
        }
    
    def rank_factors(self, factors: List[Dict], historical_data: List) -> List[Dict]:
        """因子排名"""
        evaluated = []
        for factor in factors:
            eval_result = self.evaluate_factor(factor, historical_data)
            evaluated.append(eval_result)
        
        # 按 IC * IR 排序
        evaluated.sort(key=lambda x: x.get('ic', 0) * x.get('ir', 0), reverse=True)
        return evaluated


# Alpha101 因子库（经典因子）
ALPHA_101_LIBRARY = {
    "alpha_001": "(rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) - 0.5)",
    "alpha_002": "(-1 * correlation(rank(delta(log(volume), 2)), rank(((close - open) / open)), 6))",
    "alpha_003": "(-1 * correlation(rank(open), rank(volume), 10))",
    "alpha_004": "(-1 * Ts_Rank(rank(low), 9))",
    "alpha_005": "(-1 * correlation(open, volume, 10))",
    # 更多因子...
}

# Alpha191 因子库
ALPHA_191_LIBRARY = {
    "alpha_001": "rank(-1 * delta(returns, 3))",
    "alpha_002": "rank(-1 * delta(returns, 5))",
    # 更多因子...
}


# 行业因子库
INDUSTRY_FACTORS = {
    "momentum": ["return_1m", "return_3m", "return_6m", "return_12m"],
    "volatility": ["volatility_20d", "volatility_60d", "volatility_120d"],
    "volume": ["volume_ratio", "turnover_rate", "amount"],
    "value": ["pe", "pb", "ps", "pcf", "dividend_yield"],
    "quality": ["roe", "roa", "gross_margin", "net_margin", "debt_ratio"],
    "growth": ["revenue_growth", "profit_growth", "eps_growth"],
}


def get_factor_library(factor_type: str = "all") -> Dict:
    """获取因子库"""
    if factor_type == "all":
        return {
            "alpha101": ALPHA_101_LIBRARY,
            "alpha191": ALPHA_191_LIBRARY,
            "industry": INDUSTRY_FACTORS
        }
    elif factor_type == "alpha101":
        return ALPHA_101_LIBRARY
    elif factor_type == "alpha191":
        return ALPHA_191_LIBRARY
    elif factor_type == "industry":
        return INDUSTRY_FACTORS
    return {}


# 测试
if __name__ == "__main__":
    miner = AIFactorMiner()
    
    print("🧪 测试 AI 因子生成...")
    factors = miner.generate_factors({
        "price_range": "10-50",
        "volatility": "中等",
        "volume": "活跃",
        "sector": "制造业"
    }, count=5)
    
    print(f"\n📊 生成了 {len(factors)} 个因子:")
    for i, f in enumerate(factors, 1):
        print(f"{i}. {f.get('name')}: {f.get('expression')}")
        print(f"   逻辑: {f.get('logic')}")
    
    print("\n✅ AI 因子挖掘模块测试完成")
