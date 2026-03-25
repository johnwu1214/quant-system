#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化策略模块 - 多种技术指标
"""
import pandas as pd
import numpy as np


class MAStrategy:
    """双均线策略"""
    
    def __init__(self, short_ma: int = 5, long_ma: int = 20):
        self.short_ma = short_ma
        self.long_ma = long_ma
        self.name = f"MA{short_ma}_{long_ma}"
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['ma_short'] = df['close'].rolling(window=self.short_ma).mean()
        df['ma_long'] = df['close'].rolling(window=self.long_ma).mean()
        
        df['signal'] = 0
        for i in range(1, len(df)):
            if pd.isna(df.iloc[i]['ma_short']) or pd.isna(df.iloc[i]['ma_long']):
                continue
            if pd.isna(df.iloc[i-1]['ma_short']) or pd.isna(df.iloc[i-1]['ma_long']):
                continue
            
            # 金叉
            if df.iloc[i-1]['ma_short'] <= df.iloc[i-1]['ma_long'] and \
               df.iloc[i]['ma_short'] > df.iloc[i]['ma_long']:
                df.loc[df.index[i], 'signal'] = 1
            # 死叉
            elif df.iloc[i-1]['ma_short'] >= df.iloc[i-1]['ma_long'] and \
                 df.iloc[i]['ma_short'] < df.iloc[i]['ma_long']:
                df.loc[df.index[i], 'signal'] = -1
        
        return df
    
    def get_current_signal(self, df: pd.DataFrame) -> str:
        signals = self.generate_signals(df)
        if signals.empty:
            return "无信号"
        
        last = signals.iloc[-1]
        if last['signal'] == 1:
            return "买入 (金叉)"
        elif last['signal'] == -1:
            return "卖出 (死叉)"
        return "持有"


class RSIStrategy:
    """RSI 策略"""
    
    def __init__(self, period: int = 14, oversold: int = 30, overbought: int = 70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.name = f"RSI_{period}"
    
    def calculate_rsi(self, prices: pd.Series) -> pd.Series:
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=self.period).mean()
        avg_loss = loss.rolling(window=self.period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['rsi'] = self.calculate_rsi(df['close'])
        
        df['signal'] = 0
        for i in range(1, len(df)):
            if pd.isna(df.iloc[i]['rsi']):
                continue
            
            if df.iloc[i-1]['rsi'] >= self.oversold and df.iloc[i]['rsi'] < self.oversold:
                df.loc[df.index[i], 'signal'] = 1
            elif df.iloc[i-1]['rsi'] <= self.overbought and df.iloc[i]['rsi'] > self.overbought:
                df.loc[df.index[i], 'signal'] = -1
        
        return df
    
    def get_current_signal(self, df: pd.DataFrame) -> str:
        signals = self.generate_signals(df)
        if signals.empty:
            return "无信号"
        
        last = signals.iloc[-1]
        rsi = last.get('rsi', 0)
        
        if pd.isna(rsi):
            return "无信号"
        
        if last['signal'] == 1:
            return f"买入 (RSI={rsi:.1f})"
        elif last['signal'] == -1:
            return f"卖出 (RSI={rsi:.1f})"
        return f"持有 (RSI={rsi:.1f})"


class BOLLStrategy:
    """布林带策略"""
    
    def __init__(self, period: int = 20, std_dev: int = 2):
        self.period = period
        self.std_dev = std_dev
        self.name = f"BOLL_{period}"
    
    def calculate_boll(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['ma'] = df['close'].rolling(window=self.period).mean()
        df['std'] = df['close'].rolling(window=self.period).std()
        df['upper'] = df['ma'] + self.std_dev * df['std']
        df['lower'] = df['ma'] - self.std_dev * df['std']
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self.calculate_boll(df)
        
        df['signal'] = 0
        for i in range(1, len(df)):
            if pd.isna(df.iloc[i]['upper']):
                continue
            
            # 价格突破下轨买入
            if df.iloc[i-1]['close'] >= df.iloc[i-1]['lower'] and \
               df.iloc[i]['close'] < df.iloc[i]['lower']:
                df.loc[df.index[i], 'signal'] = 1
            # 价格突破上轨卖出
            elif df.iloc[i-1]['close'] <= df.iloc[i-1]['upper'] and \
                 df.iloc[i]['close'] > df.iloc[i]['upper']:
                df.loc[df.index[i], 'signal'] = -1
        
        return df
    
    def get_current_signal(self, df: pd.DataFrame) -> str:
        df = self.calculate_boll(df)
        if df.empty or pd.isna(df.iloc[-1]['upper']):
            return "无信号"
        
        last = df.iloc[-1]
        price = last['close']
        
        if price < last['lower']:
            return f"超卖 (价格触下轨)"
        elif price > last['upper']:
            return f"超买 (价格穿上轨)"
        return "持有 (轨道内)"


class MACDStrategy:
    """MACD 策略"""
    
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self.name = "MACD"
    
    def calculate_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        exp1 = df['close'].ewm(span=self.fast, adjust=False).mean()
        exp2 = df['close'].ewm(span=self.slow, adjust=False).mean()
        
        df['macd'] = exp1 - exp2
        df['signal_line'] = df['macd'].ewm(span=self.signal, adjust=False).mean()
        df['histogram'] = df['macd'] - df['signal_line']
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self.calculate_macd(df)
        
        df['signal'] = 0
        for i in range(1, len(df)):
            if pd.isna(df.iloc[i]['macd']) or pd.isna(df.iloc[i]['signal_line']):
                continue
            
            # 金叉
            if df.iloc[i-1]['macd'] <= df.iloc[i-1]['signal_line'] and \
               df.iloc[i]['macd'] > df.iloc[i]['signal_line']:
                df.loc[df.index[i], 'signal'] = 1
            # 死叉
            elif df.iloc[i-1]['macd'] >= df.iloc[i-1]['signal_line'] and \
                 df.iloc[i]['macd'] < df.iloc[i]['signal_line']:
                df.loc[df.index[i], 'signal'] = -1
        
        return df
    
    def get_current_signal(self, df: pd.DataFrame) -> str:
        df = self.calculate_macd(df)
        if df.empty or pd.isna(df.iloc[-1]['macd']):
            return "无信号"
        
        last = df.iloc[-1]
        macd = last['macd']
        signal = last['signal_line']
        
        if macd > signal:
            return f"买入 (MACD金叉)"
        elif macd < signal:
            return f"卖出 (MACD死叉)"
        return "持有"


class VolumeStrategy:
    """成交量策略"""
    
    def __init__(self, period: int = 20):
        self.period = period
        self.name = "VOLUME"
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['vol_ma'] = df['volume'].rolling(window=self.period).mean()
        
        df['signal'] = 0
        for i in range(1, len(df)):
            if pd.isna(df.iloc[i]['vol_ma']):
                continue
            
            # 放量上涨买入
            if df.iloc[i]['volume'] > df.iloc[i]['vol_ma'] * 1.5 and \
               df.iloc[i]['close'] > df.iloc[i-1]['close']:
                df.loc[df.index[i], 'signal'] = 1
            # 缩量下跌卖出
            elif df.iloc[i]['volume'] < df.iloc[i]['vol_ma'] * 0.5 and \
                 df.iloc[i]['close'] < df.iloc[i-1]['close']:
                df.loc[df.index[i], 'signal'] = -1
        
        return df
    
    def get_current_signal(self, df: pd.DataFrame) -> str:
        if len(df) < 2:
            return "无信号"
        
        last = df.iloc[-1]
        vol_ma = last.get('volume', 0)
        
        if len(df) > 20:
            vol_ma = df['volume'].tail(20).mean()
        
        ratio = last['volume'] / vol_ma if vol_ma > 0 else 1
        
        if ratio > 1.5:
            return f"放量 ({ratio:.1f}倍)"
        elif ratio < 0.5:
            return f"缩量 ({ratio:.1f}倍)"
        return "正常"


class CompositeStrategy:
    """组合策略 - 多指标共振"""
    
    def __init__(self):
        self.strategies = [
            MAStrategy(5, 20),
            RSIStrategy(14),
            MACDStrategy(),
            BOLLStrategy()
        ]
    
    def analyze(self, df: pd.DataFrame) -> dict:
        """综合分析"""
        signals = []
        
        for s in self.strategies:
            sig = s.get_current_signal(df)
            signals.append({
                'name': s.name,
                'signal': sig,
                'is_buy': '买入' in sig,
                'is_sell': '卖出' in sig
            })
        
        # 统计信号
        buy_count = sum(1 for s in signals if s['is_buy'])
        sell_count = sum(1 for s in signals if s['is_sell'])
        
        if buy_count > sell_count and buy_count >= 2:
            final = "买入 ⬆️"
            reason = f"{buy_count}个指标看涨"
        elif sell_count > buy_count and sell_count >= 2:
            final = "卖出 ⬇️"
            reason = f"{sell_count}个指标看跌"
        else:
            final = "持有 ➡️"
            reason = "无明确方向"
        
        return {
            'signals': signals,
            'final': final,
            'reason': reason,
            'buy_count': buy_count,
            'sell_count': sell_count
        }


# 测试
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '..')
    from data_fetcher import get_stock_daily
    
    print("测试组合策略...")
    df = get_stock_daily("300001", 30)
    
    if not df.empty:
        strategy = CompositeStrategy()
        result = strategy.analyze(df)
        
        print(f"\n📊 {result['final']}")
        print(f"原因: {result['reason']}")
        print(f"看涨: {result['buy_count']}个, 看跌: {result['sell_count']}个")
        
        print("\n各指标:")
        for s in result['signals']:
            print(f"  {s['name']}: {s['signal']}")
