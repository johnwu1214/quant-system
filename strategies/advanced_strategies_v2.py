#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小龙虾量化工作室 - 进阶策略库
基于学习研究的量化策略
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


class AdvancedStrategies:
    """进阶策略集合"""
    
    @staticmethod
    def moving_average_cross(df: pd.DataFrame, short: int = 5, long: int = 20) -> Dict:
        """
        均线交叉策略
        策略逻辑：
        - 短期均线向上穿越长期均线 = 金叉 = 买入信号
        - 短期均线向下穿越长期均线 = 死叉 = 卖出信号
        """
        if len(df) < long:
            return {'signal': '数据不足', 'price': 0, 'ma_short': 0, 'ma_long': 0}
        
        df = df.copy()
        df['ma_short'] = df['close'].rolling(short).mean()
        df['ma_long'] = df['close'].rolling(long).mean()
        
        ma_short = df['ma_short'].iloc[-1]
        ma_long = df['ma_long'].iloc[-1]
        
        # 前期均线状态
        prev_short = df['ma_short'].iloc[-2]
        prev_long = df['ma_long'].iloc[-2]
        
        if prev_short <= prev_long and ma_short > ma_long:
            return {'signal': '买入 ⬆️ 金叉', 'price': df['close'].iloc[-1], 'ma_short': ma_short, 'ma_long': ma_long}
        elif prev_short >= prev_long and ma_short < ma_long:
            return {'signal': '卖出 ⬇️ 死叉', 'price': df['close'].iloc[-1], 'ma_short': ma_short, 'ma_long': ma_long}
        elif ma_short > ma_long:
            return {'signal': '持有 (多头排列)', 'price': df['close'].iloc[-1], 'ma_short': ma_short, 'ma_long': ma_long}
        else:
            return {'signal': '持有 (空头排列)', 'price': df['close'].iloc[-1], 'ma_short': ma_short, 'ma_long': ma_long}
    
    @staticmethod
    def rsi_strategy(df: pd.DataFrame, period: int = 14, oversold: int = 30, overbought: int = 70) -> Dict:
        """
        RSI相对强弱指标策略
        策略逻辑：
        - RSI < 30 = 超卖 = 买入机会
        - RSI > 70 = 超买 = 卖出风险
        - RSI 50附近 = 震荡整理
        """
        if len(df) < period:
            return {'signal': '数据不足', 'rsi': 50}
        
        df = df.copy()
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_value = rsi.iloc[-1]
        
        if rsi_value < oversold:
            return {'signal': f'买入 ⬆️ 超卖(RSI={rsi_value:.1f})', 'rsi': rsi_value}
        elif rsi_value > overbought:
            return {'signal': f'卖出 ⬇️ 超买(RSI={rsi_value:.1f})', 'rsi': rsi_value}
        else:
            return {'signal': f'持有 (RSI={rsi_value:.1f})', 'rsi': rsi_value}
    
    @staticmethod
    def macd_strategy(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """
        MACD策略
        策略逻辑：
        - DIF线上穿DEA线 = 金叉 = 买入
        - DIF线下穿DEA线 = 死叉 = 卖出
        - DIF和DEA都在0轴上方 = 多头市场
        - DIF和DEA都在0轴下方 = 空头市场
        """
        if len(df) < slow:
            return {'signal': '数据不足', 'dif': 0, 'dea': 0, 'macd': 0}
        
        df = df.copy()
        
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        
        df['dif'] = ema_fast - ema_slow
        df['dea'] = df['dif'].ewm(span=signal, adjust=False).mean()
        df['macd'] = 2 * (df['dif'] - df['dea'])
        
        dif = df['dif'].iloc[-1]
        dea = df['dea'].iloc[-1]
        
        prev_dif = df['dif'].iloc[-2]
        prev_dea = df['dea'].iloc[-2]
        
        # 金叉/死叉判断
        if prev_dif <= prev_dea and dif > dea:
            if dif > 0 and dea > 0:
                return {'signal': '买入 ⬆️ 金叉(多头)', 'dif': dif, 'dea': dea, 'macd': df['macd'].iloc[-1]}
            else:
                return {'signal': '买入 ⬆️ 金叉(反弹)', 'dif': dif, 'dea': dea, 'macd': df['macd'].iloc[-1]}
        elif prev_dif >= prev_dea and dif < dea:
            if dif < 0 and dea < 0:
                return {'signal': '卖出 ⬇️ 死叉(空头)', 'dif': dif, 'dea': dea, 'macd': df['macd'].iloc[-1]}
            else:
                return {'signal': '卖出 ⬇️ 死叉(回落)', 'dif': dif, 'dea': dea, 'macd': df['macd'].iloc[-1]}
        elif dif > dea:
            return {'signal': '持有 (多头)', 'dif': dif, 'dea': dea, 'macd': df['macd'].iloc[-1]}
        else:
            return {'signal': '持有 (空头)', 'dif': dif, 'dea': dea, 'macd': df['macd'].iloc[-1]}
    
    @staticmethod
    def boll_strategy(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Dict:
        """
        布林带策略
        策略逻辑：
        - 价格突破上轨 = 超买 = 卖出信号
        - 价格跌破下轨 = 超卖 = 买入信号
        - 价格在中轨附近 = 震荡整理
        """
        if len(df) < period:
            return {'signal': '数据不足', 'upper': 0, 'middle': 0, 'lower': 0}
        
        df = df.copy()
        
        df['middle'] = df['close'].rolling(period).mean()
        df['std'] = df['close'].rolling(period).std()
        df['upper'] = df['middle'] + std_dev * df['std']
        df['lower'] = df['middle'] - std_dev * df['std']
        
        price = df['close'].iloc[-1]
        upper = df['upper'].iloc[-1]
        middle = df['middle'].iloc[-1]
        lower = df['lower'].iloc[-1]
        
        if price > upper:
            return {'signal': '卖出 ⬇️ 超买', 'upper': upper, 'middle': middle, 'lower': lower, 'position': '上轨外'}
        elif price < lower:
            return {'signal': '买入 ⬆️ 超卖', 'upper': upper, 'middle': middle, 'lower': lower, 'position': '下轨外'}
        else:
            position = (price - lower) / (upper - lower) * 100
            if position > 66:
                return {'signal': '持有 (偏上)', 'upper': upper, 'middle': middle, 'lower': lower, 'position': f'{position:.0f}%'}
            elif position < 33:
                return {'signal': '持有 (偏下)', 'upper': upper, 'middle': middle, 'lower': lower, 'position': f'{position:.0f}%'}
            else:
                return {'signal': '持有 (中轨)', 'upper': upper, 'middle': middle, 'lower': lower, 'position': f'{position:.0f}%'}
    
    @staticmethod
    def volume_price_trend(df: pd.DataFrame) -> Dict:
        """
        量价配合策略
        策略逻辑：
        - 价涨量增 = 健康的上涨趋势
        - 价跌量缩 = 健康的下跌趋势
        - 价涨量缩 = 顶背离，可能见顶
        - 价跌量增 = 底背离，可能见底
        """
        if len(df) < 20:
            return {'signal': '数据不足', 'trend': 'unknown'}
        
        df = df.copy()
        
        # 计算涨跌幅
        df['price_change'] = df['close'].pct_change()
        
        # 计算成交量变化
        df['volume_change'] = df['volume'].pct_change()
        
        # 近期5天趋势
        recent = df.tail(5)
        
        avg_price_change = recent['price_change'].mean()
        avg_volume_change = recent['volume_change'].mean()
        
        # 判断
        if avg_price_change > 0 and avg_volume_change > 0.3:
            return {'signal': '持有 ⬆️ 价涨量增', 'trend': 'healthy_up', 'vol_ratio': 1 + avg_volume_change}
        elif avg_price_change < 0 and avg_volume_change < -0.3:
            return {'signal': '持有 ⬇️ 价跌量缩', 'trend': 'healthy_down', 'vol_ratio': 1 + avg_volume_change}
        elif avg_price_change > 0 and avg_volume_change < -0.3:
            return {'signal': '注意 ⚠️ 价涨量缩', 'trend': 'top_divergence', 'vol_ratio': 1 + avg_volume_change}
        elif avg_price_change < 0 and avg_volume_change > 0.3:
            return {'signal': '关注 🔔 价跌量增', 'trend': 'bottom_divergence', 'vol_ratio': 1 + avg_volume_change}
        else:
            return {'signal': '持有 (震荡)', 'trend': 'consolidation', 'vol_ratio': 1}
    
    @staticmethod
    def kdj_strategy(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> Dict:
        """
        KDJ随机指标策略
        策略逻辑：
        - K值 < 20 = 超卖 = 买入
        - K值 > 80 = 超买 = 卖出
        - K值上穿D值 = 金叉 = 买入
        - K值下穿D值 = 死叉 = 卖出
        """
        if len(df) < n:
            return {'signal': '数据不足', 'k': 50, 'd': 50, 'j': 50}
        
        df = df.copy()
        
        low_n = df['low'].rolling(n).min()
        high_n = df['high'].rolling(n).max()
        
        rsv = (df['close'] - low_n) / (high_n - low_n) * 100
        df['k'] = rsv.ewm(com=m1-1, adjust=False).mean()
        df['d'] = df['k'].ewm(com=m2-1, adjust=False).mean()
        df['j'] = 3 * df['k'] - 2 * df['d']
        
        k = df['k'].iloc[-1]
        d = df['d'].iloc[-1]
        j = df['j'].iloc[-1]
        
        prev_k = df['k'].iloc[-2]
        prev_d = df['d'].iloc[-2]
        
        # 金叉死叉
        if prev_k <= prev_d and k > d:
            if k < 30:
                return {'signal': '买入 ⬆️ 金叉超卖', 'k': k, 'd': d, 'j': j}
            else:
                return {'signal': '买入 ⬆️ 金叉', 'k': k, 'd': d, 'j': j}
        elif prev_k >= prev_d and k < d:
            if k > 70:
                return {'signal': '卖出 ⬇️ 死叉超买', 'k': k, 'd': d, 'j': j}
            else:
                return {'signal': '卖出 ⬇️ 死叉', 'k': k, 'd': d, 'j': j}
        elif k < 20:
            return {'signal': '买入 ⬆️ 超卖', 'k': k, 'd': d, 'j': j}
        elif k > 80:
            return {'signal': '卖出 ⬇️ 超买', 'k': k, 'd': d, 'j': j}
        else:
            return {'signal': '持有', 'k': k, 'd': d, 'j': j}
    
    @staticmethod
    def dual_indicator_confirm(df: pd.DataFrame) -> Dict:
        """
        双指标确认策略
        同时使用MACD + RSI 两个指标
        两个指标同时发出买入信号 = 强买入
        两个指标同时发出卖出信号 = 强卖出
        """
        macd = AdvancedStrategies.macd_strategy(df)
        rsi = AdvancedStrategies.rsi_strategy(df)
        
        # 判断信号强度
        buy_signals = 0
        sell_signals = 0
        
        if '买入' in macd['signal']:
            buy_signals += 1
        if '卖出' in macd['signal']:
            sell_signals += 1
        if '买入' in rsi['signal']:
            buy_signals += 1
        if '卖出' in rsi['signal']:
            sell_signals += 1
        
        if buy_signals >= 2:
            return {'signal': '强烈买入 ⬆️⬆️', 'confidence': 90, 'macd': macd['signal'], 'rsi': rsi['signal']}
        elif sell_signals >= 2:
            return {'signal': '强烈卖出 ⬇️⬇️', 'confidence': 90, 'macd': macd['signal'], 'rsi': rsi['signal']}
        elif buy_signals > sell_signals:
            return {'signal': '买入 ⬆️', 'confidence': 60, 'macd': macd['signal'], 'rsi': rsi['signal']}
        elif sell_signals > buy_signals:
            return {'signal': '卖出 ⬇️', 'confidence': 60, 'macd': macd['signal'], 'rsi': rsi['signal']}
        else:
            return {'signal': '持有 ➡️', 'confidence': 30, 'macd': macd['signal'], 'rsi': rsi['signal']}


class RiskManagement:
    """风险管理系统"""
    
    @staticmethod
    def calculate_position_size(capital: float, price: float, risk_pct: float = 0.02) -> int:
        """
        仓位管理 - 根据风险计算买入股数
        每次交易最多承受2%的亏损
        """
        max_loss = capital * risk_pct
        shares = int(max_loss / (price * 0.05))  # 假设止损5%
        return shares
    
    @staticmethod
    def stop_loss(buy_price: float, current_price: float, stop_pct: float = 0.05) -> Dict:
        """
        止损策略
        默认止损线：-5%
        """
        loss_pct = (current_price - buy_price) / buy_price
        
        if loss_pct <= -stop_pct:
            return {
                'action': '止损 ⛔',
                'loss_pct': loss_pct * 100,
                'reason': f'亏损达到{abs(loss_pct*100):.1f}%'
            }
        elif loss_pct <= -stop_pct / 2:
            return {
                'action': '预警 ⚠️',
                'loss_pct': loss_pct * 100,
                'reason': '接近止损线'
            }
        else:
            return {
                'action': '持有 ✅',
                'loss_pct': loss_pct * 100,
                'reason': '正常波动'
            }
    
    @staticmethod
    def take_profit(buy_price: float, current_price: float, base_pct: float = 0.10) -> Dict:
        """
        止盈策略
        默认止盈线：+10%
        可根据盈利幅度调整
        """
        profit_pct = (current_price - buy_price) / buy_price
        
        if profit_pct >= base_pct * 2:
            return {
                'action': '分批卖出 📤',
                'profit_pct': profit_pct * 100,
                'reason': '盈利已达20%，可考虑部分止盈'
            }
        elif profit_pct >= base_pct:
            return {
                'action': '持有 ✅',
                'profit_pct': profit_pct * 100,
                'reason': '已达到止盈目标，可继续持有'
            }
        else:
            return {
                'action': '持有 🔒',
                'profit_pct': profit_pct * 100,
                'reason': '未达到止盈线'
            }


class CompositeSignal:
    """综合信号系统"""
    
    def __init__(self):
        self.strategies = AdvancedStrategies()
        self.risk = RiskManagement()
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """综合分析"""
        results = {
            'signals': {},
            'buy_score': 0,
            'sell_score': 0,
            'decision': '持有',
            'confidence': 0
        }
        
        # 各指标分析
        signal_list = [
            ('MA均线', self.strategies.moving_average_cross(df)),
            ('RSI', self.strategies.rsi_strategy(df)),
            ('MACD', self.strategies.macd_strategy(df)),
            ('BOLL', self.strategies.boll_strategy(df)),
            ('KDJ', self.strategies.kdj_strategy(df)),
            ('量价', self.strategies.volume_price_trend(df)),
        ]
        
        for name, signal in signal_list:
            results['signals'][name] = signal['signal']
            
            if '买入' in signal['signal']:
                results['buy_score'] += 1
            elif '卖出' in signal['signal']:
                results['sell_score'] += 1
        
        # 综合决策
        bs = results['buy_score']
        ss = results['sell_score']
        
        if bs >= 4:
            results['decision'] = '强烈买入 ⬆️⬆️'
            results['confidence'] = min(bs * 20, 95)
        elif bs > ss:
            results['decision'] = '买入 ⬆️'
            results['confidence'] = 50 + (bs - ss) * 15
        elif ss >= 4:
            results['decision'] = '强烈卖出 ⬇️⬇️'
            results['confidence'] = min(ss * 20, 95)
        elif ss > bs:
            results['decision'] = '卖出 ⬇️'
            results['confidence'] = 50 + (ss - bs) * 15
        else:
            results['decision'] = '持有 ➡️'
            results['confidence'] = 30
        
        return results


# 测试
if __name__ == "__main__":
    print("✅ 进阶策略库已加载")
    print("\n可用策略:")
    print("  1. 均线交叉 (MA Cross)")
    print("  2. RSI相对强弱")
    print("  3. MACD")
    print("  4. 布林带 (BOLL)")
    print("  5. KDJ随机指标")
    print("  6. 量价配合")
    print("  7. 双指标确认")
    print("\n风控模块:")
    print("  - 仓位管理")
    print("  - 止损策略")
    print("  - 止盈策略")
