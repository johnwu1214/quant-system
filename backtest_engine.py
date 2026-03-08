#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略回测系统
验证策略有效性
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import get_daily_tushare


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, 
                 initial_capital: float = 100000,
                 commission: float = 0.0003,
                 slippage: float = 0.001):
        """
        初始化
        
        Args:
            initial_capital: 初始资金
            commission: 佣金费率 (万3)
            slippage: 滑点 (千1)
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
    
    def run_ma_cross_backtest(self, df: pd.DataFrame, 
                              short_ma: int = 5, 
                              long_ma: int = 20) -> Dict:
        """
        均线交叉策略回测
        
        买入: 短期均线上穿长期均线
        卖出: 短期均线下穿长期均线
        """
        df = df.copy()
        
        # 计算均线
        df['ma_short'] = df['close'].rolling(short_ma).mean()
        df['ma_long'] = df['close'].rolling(long_ma).mean()
        
        # 生成信号
        df['signal'] = 0
        df.loc[df['ma_short'] > df['ma_long'], 'signal'] = 1  # 多头
        df.loc[df['ma_short'] < df['ma_long'], 'signal'] = -1  # 空头
        
        # 交易信号
        df['trade'] = df['signal'].diff()
        
        # 模拟交易
        capital = self.initial_capital
        position = 0
        trades = []
        equity = []
        
        for i in range(long_ma, len(df)):
            price = df['close'].iloc[i]
            
            # 买入信号
            if df['trade'].iloc[i] == 2 and capital > price * 100:
                shares = int(capital * 0.95 / price / 100) * 100
                cost = shares * price * (1 + self.commission + self.slippage)
                if cost <= capital:
                    capital -= cost
                    position = shares
                    trades.append({
                        'date': str(df['date'].iloc[i])[:10],
                        'action': 'BUY',
                        'price': price,
                        'shares': shares
                    })
            
            # 卖出信号
            elif df['trade'].iloc[i] == -2 and position > 0:
                revenue = position * price * (1 - self.commission - self.slippage)
                capital += revenue
                trades.append({
                    'date': str(df['date'].iloc[i])[:10],
                    'action': 'SELL',
                    'price': price,
                    'shares': position,
                    'profit': revenue - position * df['close'].iloc[i-1]
                })
                position = 0
            
            # 记录权益
            value = capital + position * price
            equity.append({
                'date': str(df['date'].iloc[i])[:10],
                'value': value,
                'return_pct': (value - self.initial_capital) / self.initial_capital * 100
            })
        
        # 最终权益
        final_value = capital + position * df['close'].iloc[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100
        
        # 计算统计
        winning = len([t for t in trades if t.get('profit', 0) > 0])
        losing = len([t for t in trades if t.get('profit', 0) < 0])
        
        return {
            'strategy': f'MA{short_ma}/{long_ma}交叉',
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return_pct': total_return,
            'total_trades': len(trades),
            'winning_trades': winning,
            'losing_trades': losing,
            'win_rate': winning / (winning + losing) * 100 if winning + losing > 0 else 0,
            'trades': trades[-10:],
            'equity_curve': equity[-30:]
        }
    
    def run_rsi_backtest(self, df: pd.DataFrame, 
                         period: int = 14,
                         oversold: int = 30,
                         overbought: int = 70) -> Dict:
        """
        RSI策略回测
        
        买入: RSI < oversold
        卖出: RSI > overbought
        """
        df = df.copy()
        
        # 计算RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 信号
        df['signal'] = 0
        df.loc[df['rsi'] < oversold, 'signal'] = 1
        df.loc[df['rsi'] > overbought, 'signal'] = -1
        
        # 交易
        capital = self.initial_capital
        position = 0
        trades = []
        
        for i in range(period + 1, len(df)):
            price = df['close'].iloc[i]
            
            # 买入
            if df['signal'].iloc[i] == 1 and capital > price * 100 and position == 0:
                shares = int(capital * 0.95 / price / 100) * 100
                cost = shares * price * (1 + self.commission + self.slippage)
                if cost <= capital:
                    capital -= cost
                    position = shares
                    trades.append({
                        'date': str(df['date'].iloc[i])[:10],
                        'action': 'BUY',
                        'price': price,
                        'shares': shares
                    })
            
            # 卖出
            elif df['signal'].iloc[i] == -1 and position > 0:
                revenue = position * price * (1 - self.commission - self.slippage)
                capital += revenue
                trades.append({
                    'date': str(df['date'].iloc[i])[:10],
                    'action': 'SELL',
                    'price': price,
                    'shares': position,
                    'profit': revenue - position * df['close'].iloc[i-1]
                })
                position = 0
        
        final_value = capital + position * df['close'].iloc[-1]
        
        return {
            'strategy': f'RSI({period})',
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return_pct': (final_value - self.initial_capital) / self.initial_capital * 100,
            'total_trades': len(trades)
        }
    
    def run_macd_backtest(self, df: pd.DataFrame) -> Dict:
        """
        MACD策略回测
        
        买入: DIF上穿DEA (金叉)
        卖出: DIF下穿DEA (死叉)
        """
        df = df.copy()
        
        # MACD
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['dif'] = ema12 - ema26
        df['dea'] = df['dif'].ewm(span=9, adjust=False).mean()
        df['macd'] = 2 * (df['dif'] - df['dea'])
        
        # 信号
        df['signal'] = 0
        df.loc[df['dif'] > df['dea'], 'signal'] = 1
        df.loc[df['dif'] < df['dea'], 'signal'] = -1
        
        df['trade'] = df['signal'].diff()
        
        # 交易
        capital = self.initial_capital
        position = 0
        trades = []
        
        for i in range(30, len(df)):
            price = df['close'].iloc[i]
            
            if df['trade'].iloc[i] == 2 and capital > price * 100 and position == 0:
                shares = int(capital * 0.95 / price / 100) * 100
                cost = shares * price * (1 + self.commission + self.slippage)
                if cost <= capital:
                    capital -= cost
                    position = shares
                    trades.append({
                        'date': str(df['date'].iloc[i])[:10],
                        'action': 'BUY',
                        'price': price
                    })
            
            elif df['trade'].iloc[i] == -2 and position > 0:
                revenue = position * price * (1 - self.commission - self.slippage)
                capital += revenue
                trades.append({
                    'date': str(df['date'].iloc[i])[:10],
                    'action': 'SELL',
                    'price': price
                })
                position = 0
        
        final_value = capital + position * df['close'].iloc[-1]
        
        return {
            'strategy': 'MACD',
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return_pct': (final_value - self.initial_capital) / self.initial_capital * 100,
            'total_trades': len(trades)
        }


def run_stock_backtest(stock_code: str, days: int = 365) -> Dict:
    """运行股票回测"""
    # 获取数据
    df = get_daily_tushare(stock_code, days + 30)
    if df.empty:
        return {'error': '数据获取失败'}
    
    df = df.sort_values('date').reset_index(drop=True)
    
    # 回测
    engine = BacktestEngine(100000)
    
    results = {
        'stock_code': stock_code,
        'period_days': days,
        'ma_cross': engine.run_ma_cross_backtest(df),
        'rsi': engine.run_rsi_backtest(df),
        'macd': engine.run_macd_backtest(df)
    }
    
    return results


if __name__ == "__main__":
    import json
    
    # 测试
    print("开始回测...")
    result = run_stock_backtest('603960', 180)
    
    if 'error' not in result:
        print(f"\n📊 回测结果 - {result['stock_code']}")
        print(f"\nMA策略: {result['ma_cross']['total_return_pct']:.1f}%")
        print(f"RSI策略: {result['rsi']['total_return_pct']:.1f}%")
        print(f"MACD策略: {result['macd']['total_return_pct']:.1f}%")
    else:
        print(f"错误: {result['error']}")
