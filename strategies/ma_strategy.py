#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双均线交叉策略
"""
import pandas as pd
import numpy as np

class MAStrategy:
    """双均线策略"""
    
    def __init__(self, short_ma: int = 5, long_ma: int = 20):
        self.short_ma = short_ma  # 短期均线
        self.long_ma = long_ma    # 长期均线
        self.name = f"MA{short_ma}_{long_ma}"
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        Returns:
            DataFrame with columns: date, signal (1=买入, -1=卖出, 0=持有)
        """
        df = df.copy()
        
        # 计算均线
        df['ma_short'] = df['close'].rolling(window=self.short_ma).mean()
        df['ma_long'] = df['close'].rolling(window=self.long_ma).mean()
        
        # 初始化信号
        df['signal'] = 0
        
        # 金叉买入，死叉卖出
        for i in range(1, len(df)):
            if pd.isna(df.iloc[i]['ma_short']) or pd.isna(df.iloc[i]['ma_long']):
                continue
            if pd.isna(df.iloc[i-1]['ma_short']) or pd.isna(df.iloc[i-1]['ma_long']):
                continue
                
            # 金叉：短期均线从下穿过长期均线
            if df.iloc[i-1]['ma_short'] <= df.iloc[i-1]['ma_long'] and \
               df.iloc[i]['ma_short'] > df.iloc[i]['ma_long']:
                df.loc[df.index[i], 'signal'] = 1  # 买入
            
            # 死叉：短期均线从上穿过长期均线
            elif df.iloc[i-1]['ma_short'] >= df.iloc[i-1]['ma_long'] and \
                 df.iloc[i]['ma_short'] < df.iloc[i]['ma_long']:
                df.loc[df.index[i], 'signal'] = -1  # 卖出
        
        return df
    
    def get_current_signal(self, df: pd.DataFrame) -> str:
        """获取当前信号"""
        signals = self.generate_signals(df)
        if signals.empty:
            return "无信号"
        
        last_signal = signals.iloc[-1]['signal']
        if last_signal == 1:
            return "买入"
        elif last_signal == -1:
            return "卖出"
        return "持有"


class RSIStrategy:
    """RSI 策略"""
    
    def __init__(self, period: int = 14, oversold: int = 30, overbought: int = 70):
        self.period = period
        self.oversold = oversold    # 超卖阈值
        self.overbought = overbought # 超买阈值
        self.name = f"RSI_{period}"
    
    def calculate_rsi(self, prices: pd.Series) -> pd.Series:
        """计算RSI"""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=self.period).mean()
        avg_loss = loss.rolling(window=self.period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号"""
        df = df.copy()
        df['rsi'] = self.calculate_rsi(df['close'])
        
        df['signal'] = 0
        for i in range(1, len(df)):
            if pd.isna(df.iloc[i]['rsi']):
                continue
            
            # RSI < 30 超卖，买入
            if df.iloc[i-1]['rsi'] >= self.oversold and df.iloc[i]['rsi'] < self.oversold:
                df.loc[df.index[i], 'signal'] = 1
            
            # RSI > 70 超买，卖出
            elif df.iloc[i-1]['rsi'] <= self.overbought and df.iloc[i]['rsi'] > self.overbought:
                df.loc[df.index[i], 'signal'] = -1
        
        return df
    
    def get_current_signal(self, df: pd.DataFrame) -> str:
        """获取当前信号"""
        signals = self.generate_signals(df)
        if signals.empty:
            return "无信号"
        
        last_signal = signals.iloc[-1]['signal']
        last_rsi = signals.iloc[-1]['rsi']
        
        if last_signal == 1:
            return f"买入 (RSI={last_rsi:.1f})"
        elif last_signal == -1:
            return f"卖出 (RSI={last_rsi:.1f})"
        return f"持有 (RSI={last_rsi:.1f})"


if __name__ == "__main__":
    # 测试
    from data_fetcher import get_stock_daily
    
    print("获取数据...")
    df = get_stock_daily("600519", 100)
    
    print("\n=== 均线策略 ===")
    ma_strategy = MAStrategy(5, 20)
    signal = ma_strategy.get_current_signal(df)
    print(f"信号: {signal}")
    
    print("\n=== RSI 策略 ===")
    rsi_strategy = RSIStrategy(14)
    signal = rsi_strategy.get_current_signal(df)
    print(f"信号: {signal}")
