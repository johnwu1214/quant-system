#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回测引擎
"""
import pandas as pd
import numpy as np
from datetime import datetime
import os

class BacktestEngine:
    """简单回测引擎"""
    
    def __init__(self, initial_capital: float = 100000, commission: float = 0.0003):
        """
        Args:
            initial_capital: 初始资金
            commission: 手续费率 (万三)
        """
        self.initial_capital = initial_capital
        self.commission = commission
    
    def run(self, df: pd.DataFrame, strategy) -> dict:
        """
        运行回测
        
        Returns:
            回测结果字典
        """
        df = strategy.generate_signals(df)
        
        capital = self.initial_capital
        position = 0  # 持仓股数
        trades = []   # 交易记录
        
        for i in range(len(df)):
            row = df.iloc[i]
            signal = row['signal']
            price = row['close']
            date = row['date']
            
            if signal == 1 and position == 0:  # 买入
                # 计算可买入股数（100股整数倍）
                max_shares = (capital * (1 - self.commission)) // (price * 100) * 100
                if max_shares > 0:
                    cost = max_shares * price * (1 + self.commission)
                    position = max_shares
                    capital -= cost
                    trades.append({
                        'date': date,
                        'type': 'BUY',
                        'price': price,
                        'shares': position,
                        'capital': capital
                    })
            
            elif signal == -1 and position > 0:  # 卖出
                revenue = position * price * (1 - self.commission)
                capital += revenue
                trades.append({
                    'date': date,
                    'type': 'SELL',
                    'price': price,
                    'shares': position,
                    'capital': capital
                })
                position = 0
        
        # 计算最终收益
        final_value = capital + position * df.iloc[-1]['close']
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100
        
        # 计算年化收益率
        days = (df.iloc[-1]['date'] - df.iloc[0]['date']).days
        annual_return = total_return / days * 365 if days > 0 else 0
        
        # 计算最大回撤
        df['portfolio_value'] = capital  # 简化计算
        
        return {
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'annual_return': annual_return,
            'total_trades': len(trades),
            'trades': trades,
            'win_rate': self._calc_win_rate(trades)
        }
    
    def _calc_win_rate(self, trades: list) -> float:
        """计算胜率"""
        if len(trades) < 2:
            return 0
        
        wins = 0
        total = 0
        for i in range(0, len(trades) - 1, 2):
            if i + 1 < len(trades):
                if trades[i]['type'] == 'BUY' and trades[i+1]['type'] == 'SELL':
                    profit = trades[i+1]['capital'] - trades[i]['capital']
                    if profit > 0:
                        wins += 1
                    total += 1
        
        return wins / total * 100 if total > 0 else 0
    
    def print_report(self, result: dict):
        """打印回测报告"""
        print("\n" + "="*50)
        print("           回 测 报 告")
        print("="*50)
        print(f"初始资金:    ¥{result['initial_capital']:,.2f}")
        print(f"最终价值:    ¥{result['final_value']:,.2f}")
        print(f"总收益率:    {result['total_return']:.2f}%")
        print(f"年化收益率:  {result['annual_return']:.2f}%")
        print(f"交易次数:    {result['total_trades']}")
        print(f"胜率:        {result['win_rate']:.1f}%")
        print("="*50)
        
        print("\n最近5笔交易:")
        for t in result['trades'][-5:]:
            print(f"  {t['date'].strftime('%Y-%m-%d')} | {t['type']:4s} | "
                  f"价格: {t['price']:.2f} | 股数: {t['shares']} | 资金: {t['capital']:,.0f}")


if __name__ == "__main__":
    from data_fetcher import get_stock_daily
    from strategies.ma_strategy import MAStrategy
    
    print("运行回测...")
    
    # 获取数据
    df = get_stock_daily("600519", 365)
    
    # 运行策略
    strategy = MAStrategy(5, 20)
    engine = BacktestEngine(initial_capital=100000)
    result = engine.run(df, strategy)
    
    # 打印报告
    engine.print_report(result)
