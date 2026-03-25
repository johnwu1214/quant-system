#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib Alpha158 因子库集成
基于Qlib的成熟因子体系
"""
import os
import sys
import pandas as pd
import numpy as np
from typing import Dict, List

# 尝试导入 Qlib
try:
    import qlib
    from qlib.data import D
    QLIB_AVAILABLE = True
except ImportError:
    QLIB_AVAILABLE = False
    print("⚠️ Qlib 未安装")


# ==================== Alpha158 因子库 ====================

class Alpha158Factors:
    """Alpha158 因子库 - 158个预定义因子"""
    
    # 基础价格因子
    PRICE_FACTORS = [
        "$close", "$open", "$high", "$low", "$volume"
    ]
    
    # 收益率因子 (1-60天)
    RETURN_FACTORS = [
        "Ref($close, 1)/Ref($close, 2)-1",  # 1日收益率
        "Ref($close, 5)/Ref($close, 10)-1",  # 5日收益率
        "Ref($close, 10)/Ref($close, 20)-1", # 10日收益率
        "Ref($close, 20)/Ref($close, 60)-1", # 20日收益率
    ]
    
    # 波动率因子
    VOLATILITY_FACTORS = [
        "Std($close, 5)",   # 5日波动率
        "Std($close, 10)",  # 10日波动率
        "Std($close, 20)",  # 20日波动率
    ]
    
    # 动量因子
    MOMENTUM_FACTORS = [
        "($close-Ref($close, 5))/Ref($close, 5)",   # 5日动量
        "($close-Ref($close, 10))/Ref($close, 10)", # 10日动量
        "($close-Ref($close, 20))/Ref($close, 20)", # 20日动量
    ]
    
    # 成交量因子
    VOLUME_FACTORS = [
        "Mean($volume, 5)",    # 5日均量
        "Mean($volume, 10)",   # 10日均量
        "Std($volume, 5)",     # 5日成交量波动
        "$volume/Ref($volume, 1)-1",  # 量比
    ]
    
    # 技术指标因子
    TECHNICAL_FACTORS = [
        # MACD
        "EMA($close, 12) - EMA($close, 26)",  # DIF
        "EMA(DEMA($close, 12), 9) - EMA($close, 26)",  # DEA
        # RSI
        "RSI($close, 6)",   # RSI-6
        "RSI($close, 12)",  # RSI-12
        # 布林带
        "($close - Mean($close, 20)) / Std($close, 20)",  # BOLL位置
        "Mean($close, 20) + 2*Std($close, 20)",  # 上轨
        "Mean($close, 20) - 2*Std($close, 20)",  # 下轨
    ]
    
    @classmethod
    def get_all_factors(cls) -> Dict[str, List[str]]:
        """获取所有因子"""
        return {
            "price": cls.PRICE_FACTORS,
            "return": cls.RETURN_FACTORS,
            "volatility": cls.VOLATILITY_FACTORS,
            "momentum": cls.MOMENTUM_FACTORS,
            "volume": cls.VOLUME_FACTORS,
            "technical": cls.TECHNICAL_FACTORS,
        }
    
    @classmethod
    def get_factor_count(cls) -> int:
        """获取因子总数"""
        factors = cls.get_all_factors()
        return sum(len(v) for v in factors.values())


# ==================== 自定义技术因子 ====================

class TechnicalFactors:
    """自定义技术因子计算器"""
    
    @staticmethod
    def calculate_ma(df: pd.DataFrame, periods: List[int] = [5, 10, 20, 60]) -> pd.DataFrame:
        """计算移动平均线"""
        result = df.copy()
        for p in periods:
            result[f'ma{p}'] = df['close'].rolling(p).mean()
        return result
    
    @staticmethod
    def calculate_ema(df: pd.DataFrame, periods: List[int] = [12, 26]) -> pd.DataFrame:
        """计算指数移动平均"""
        result = df.copy()
        for p in periods:
            result[f'ema{p}'] = df['close'].ewm(span=p, adjust=False).mean()
        return result
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, periods: List[int] = [6, 12, 24]) -> pd.DataFrame:
        """计算RSI"""
        result = df.copy()
        for p in periods:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(p).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(p).mean()
            rs = gain / loss
            result[f'rsi{p}'] = 100 - (100 / (1 + rs))
        return result
    
    @staticmethod
    def calculate_macd(df: pd.DataFrame) -> pd.DataFrame:
        """计算MACD"""
        result = df.copy()
        
        # DIF
        result['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
        result['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
        result['dif'] = result['ema12'] - result['ema26']
        
        # DEA
        result['dea'] = result['dif'].ewm(span=9, adjust=False).mean()
        
        # MACD柱
        result['macd'] = 2 * (result['dif'] - result['dea'])
        
        return result
    
    @staticmethod
    def calculate_boll(df: pd.DataFrame, period: int = 20, std_dev: float = 2) -> pd.DataFrame:
        """计算布林带"""
        result = df.copy()
        
        result['bb_mid'] = df['close'].rolling(period).mean()
        result['bb_std'] = df['close'].rolling(period).std()
        result['bb_upper'] = result['bb_mid'] + std_dev * result['bb_std']
        result['bb_lower'] = result['bb_mid'] - std_dev * result['bb_std']
        result['bb_position'] = (df['close'] - result['bb_lower']) / (result['bb_upper'] - result['bb_lower'])
        
        return result
    
    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """计算ATR"""
        result = df.copy()
        
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        result['atr'] = true_range.rolling(period).mean()
        
        return result
    
    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        """计算所有自定义因子"""
        result = df.copy()
        
        result = TechnicalFactors.calculate_ma(result)
        result = TechnicalFactors.calculate_ema(result)
        result = TechnicalFactors.calculate_rsi(result)
        result = TechnicalFactors.calculate_macd(result)
        result = TechnicalFactors.calculate_boll(result)
        result = TechnicalFactors.calculate_atr(result)
        
        return result


# ==================== 因子有效性评估 ====================

class FactorEvaluator:
    """因子有效性评估"""
    
    @staticmethod
    def calculate_ic(predictions: pd.Series, returns: pd.Series) -> float:
        """计算IC (Information Coefficient)"""
        # 简化实现
        if len(predictions) != len(returns) or len(predictions) < 10:
            return 0.0
        
        # 转换为numpy数组
        pred = predictions.values
        ret = returns.values
        
        # 去除NaN
        mask = ~(np.isnan(pred) | np.isnan(ret))
        if mask.sum() < 10:
            return 0.0
        
        # 计算相关系数
        ic = np.corrcoef(pred[mask], ret[mask])[0, 1]
        return ic if not np.isnan(ic) else 0.0
    
    @staticmethod
    def calculate_rank_ic(predictions: pd.Series, returns: pd.Series) -> float:
        """计算Rank IC"""
        if len(predictions) != len(returns) or len(predictions) < 10:
            return 0.0
        
        from scipy.stats import spearmanr
        ic, _ = spearmanr(predictions, returns, nan_policy='omit')
        return ic if not np.isnan(ic) else 0.0
    
    @staticmethod
    def evaluate_factor(factor_values: pd.Series, forward_returns: pd.Series) -> Dict:
        """评估单个因子"""
        ic = FactorEvaluator.calculate_ic(factor_values, forward_returns)
        rank_ic = FactorEvaluator.calculate_rank_ic(factor_values, forward_returns)
        
        return {
            "ic": ic,
            "rank_ic": rank_ic,
            "ic_std": factor_values.std(),
            "valid": abs(ic) > 0.02,  # IC > 2% 认为有效
            "direction": "正向" if ic > 0 else "负向"
        }


# ==================== 因子组合器 ====================

class FactorComposer:
    """因子组合器"""
    
    def __init__(self):
        self.factors = {}
    
    def add_factor(self, name: str, values: pd.Series):
        """添加因子"""
        self.factors[name] = values
    
    def normalize(self, method: str = "zscore") -> pd.DataFrame:
        """标准化因子"""
        df = pd.DataFrame(self.factors)
        
        if method == "zscore":
            # Z-score 标准化
            return (df - df.mean()) / df.std()
        elif method == "rank":
            # 排序标准化
            return df.rank(pct=True)
        
        return df
    
    def weighted_sum(self, weights: Dict[str, float]) -> pd.Series:
        """加权求和"""
        df = self.normalize()
        
        result = pd.Series(0, index=df.index)
        for name, weight in weights.items():
            if name in df.columns:
                result += df[name] * weight
        
        return result
    
    def get_composite_score(self, 
                          momentum_weight: float = 0.3,
                          value_weight: float = 0.3,
                          quality_weight: float = 0.2,
                          technical_weight: float = 0.2) -> pd.Series:
        """获取综合得分"""
        
        scores = {}
        
        # 动量得分
        momentum_cols = [c for c in self.factors.keys() if 'return' in c or 'momentum' in c]
        if momentum_cols:
            scores['momentum'] = self.factors[momentum_cols[0]]
        
        # 价值得分
        value_cols = [c for c in self.factors.keys() if 'pe' in c or 'pb' in c]
        if value_cols:
            scores['value'] = self.factors[value_cols[0]]
        
        # 质量得分
        quality_cols = [c for c in self.factors.keys() if 'roe' in c or 'gross_margin' in c]
        if quality_cols:
            scores['quality'] = self.factors[quality_cols[0]]
        
        # 技术得分
        tech_cols = [c for c in self.factors.keys() if any(x in c for x in ['rsi', 'macd', 'boll'])]
        if tech_cols:
            scores['technical'] = self.factors[tech_cols[0]]
        
        # 加权
        result = pd.Series(0, index=next(iter(self.factors.values())).index)
        if 'momentum' in scores:
            result += scores['momentum'] * momentum_weight
        if 'value' in scores:
            result += scores['value'] * value_weight
        if 'quality' in scores:
            result += scores['quality'] * quality_weight
        if 'technical' in scores:
            result += scores['technical'] * technical_weight
        
        return result


# 测试
if __name__ == "__main__":
    print("🧪 测试因子库...")
    
    # 测试 Alpha158
    print(f"\n📊 Alpha158 因子库:")
    factors = Alpha158Factors.get_all_factors()
    for name, flist in factors.items():
        print(f"   {name}: {len(flist)} 个")
    print(f"   总计: {Alpha158Factors.get_factor_count()} 个")
    
    # 测试技术因子计算
    print("\n📈 测试技术因子:")
    # 模拟数据
    import numpy as np
    dates = pd.date_range('2025-01-01', periods=100)
    df = pd.DataFrame({
        'date': dates,
        'open': np.random.uniform(10, 20, 100),
        'high': np.random.uniform(10, 20, 100),
        'low': np.random.uniform(10, 20, 100),
        'close': np.random.uniform(10, 20, 100),
        'volume': np.random.uniform(1000000, 10000000, 100)
    })
    
    result = TechnicalFactors.calculate_all(df)
    print(f"   计算完成: {len(result.columns)} 列")
    
    print("\n✅ 因子库测试完成")
