#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网格交易策略
适用于震荡行情，低买高卖赚取差价
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


class GridTrading:
    """
    网格交易策略
    
    原理：
    - 在震荡行情中，将价格区间分成若干格子
    - 价格每下跌一格买入，每上涨一格卖出
    - 赚取波动收益
    
    优点：
    - 不用预测涨跌方向
    - 震荡行情收益稳定
    - 风险相对可控
    """
    
    def __init__(self, 
                 grid_count: int = 10,
                 grid_pct: float = 0.02,
                 max_position: float = 1.0,
                 min_position: float = 0.0):
        """
        初始化网格交易策略
        
        Args:
            grid_count: 网格数量
            grid_pct: 每个网格的百分比跨度 (如0.02=2%)
            max_position: 最大仓位 (1.0=100%)
            min_position: 最小仓位 (0.0=空仓)
        """
        self.grid_count = grid_count
        self.grid_pct = grid_pct
        self.max_position = max_position
        self.min_position = min_position
        
    def calculate_grids(self, current_price: float, volatility: float = 0.1) -> Dict:
        """
        计算网格区间
        
        Args:
            current_price: 当前价格
            volatility: 波动率 (默认10%)
            
        Returns:
            网格上下限和各格子价格
        """
        # 根据波动率确定区间
        upper = current_price * (1 + volatility * 2)
        lower = current_price * (1 - volatility * 2)
        
        # 生成网格价格
        grid_prices = []
        step = (upper - lower) / self.grid_count
        
        for i in range(self.grid_count + 1):
            grid_prices.append(lower + step * i)
        
        return {
            'current_price': current_price,
            'upper': upper,
            'lower': lower,
            'grids': grid_prices,
            'grid_step': step,
            'step_pct': self.grid_pct * 100
        }
    
    def get_signal(self, price: float, position: float, grids: List[float]) -> Dict:
        """
        获取交易信号
        
        Args:
            price: 当前价格
            position: 当前持仓比例 (0-1)
            grids: 网格价格列表
            
        Returns:
            交易信号
        """
        # 找到当前价格所在的格子
        current_grid = 0
        for i, grid_price in enumerate(grids):
            if price >= grid_price:
                current_grid = i
        
        # 决策逻辑
        if position < self.max_position and current_grid <= self.grid_count // 3:
            # 价格在底部区域，且未满仓 → 买入
            action = '买入 ⬆️'
            reason = f'价格位于底部格子{current_grid}，建议加仓'
        elif position > self.min_position and current_grid >= self.grid_count * 2 // 3:
            # 价格在顶部区域，且有持仓 → 卖出
            action = '卖出 ⬇️'
            reason = f'价格位于顶部格子{current_grid}，建议减仓'
        elif position > self.min_position and price < grids[0] * 1.02:
            # 价格跌破最低格2%以内 → 止损
            action = '止损 ⛔'
            reason = '价格跌破支撑位'
        else:
            action = '持有 ➡️'
            reason = f'价格在中间区域，格子位置={current_grid}'
        
        return {
            'action': action,
            'reason': reason,
            'current_grid': current_grid,
            'total_grids': self.grid_count,
            'position': position
        }
    
    def backtest(self, df: pd.DataFrame, initial_capital: float = 100000) -> Dict:
        """
        回测网格交易策略
        
        Args:
            df: 包含收盘价的数据
            initial_capital: 初始资金
            
        Returns:
            回测结果
        """
        capital = initial_capital
        position = 0  # 持仓数量
        grid_prices = None
        
        trades = []
        
        for i in range(20, len(df)):  # 从第20天开始
            current_price = df['close'].iloc[i]
            
            # 初始化网格（只用一次）
            if grid_prices is None:
                grids = self.calculate_grids(current_price)['grids']
                grid_prices = grids
            
            # 计算当前持仓市值
            position_value = position * current_price
            total_value = capital + position_value
            position_ratio = position_value / total_value if total_value > 0 else 0
            
            # 获取信号
            signal = self.get_signal(current_price, position_ratio, grid_prices)
            
            # 执行交易
            if signal['action'] == '买入 ⬆️' and capital > current_price * 100:
                # 买入1手
                shares = 100
                cost = shares * current_price
                if cost <= capital:
                    capital -= cost
                    position += shares
                    trades.append({
                        'day': i,
                        'action': '买入',
                        'price': current_price,
                        'shares': shares
                    })
                    
            elif signal['action'] == '卖出 ⬇️' and position >= 100:
                # 卖出1手
                shares = 100
                revenue = shares * current_price
                capital += revenue
                position -= shares
                trades.append({
                    'day': i,
                    'action': '卖出',
                    'price': current_price,
                    'shares': shares
                })
        
        # 最终资产
        final_value = capital + position * df['close'].iloc[-1]
        return_pct = (final_value - initial_capital) / initial_capital * 100
        
        return {
            'initial_capital': initial_capital,
            'final_value': final_value,
            'return_pct': return_pct,
            'total_trades': len(trades),
            'trades': trades[-10:]  # 最近10笔
        }


class GridWithTrend:
    """
    趋势增强版网格交易
    结合趋势判断，只在趋势有利时开仓
    """
    
    def __init__(self):
        self.grid = GridTrading()
    
    def get_trend(self, df: pd.DataFrame) -> str:
        """判断趋势"""
        if len(df) < 20:
            return 'unknown'
        
        ma5 = df['close'].rolling(5).mean().iloc[-1]
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        
        if ma5 > ma20:
            return 'up'
        elif ma5 < ma20:
            return 'down'
        else:
            return 'sideways'
    
    def analyze(self, df: pd.DataFrame, current_price: float) -> Dict:
        """
        综合分析
        
        Returns:
            包含趋势判断、网格信号、综合决策
        """
        trend = self.get_trend(df)
        grids = self.grid.calculate_grids(current_price)
        
        # 趋势信号
        if trend == 'up':
            trend_signal = '上涨趋势 📈'
        elif trend == 'down':
            trend_signal = '下跌趋势 📉'
        else:
            trend_signal = '震荡整理 ➡️'
        
        # 综合决策
        if trend == 'up':
            # 上涨趋势：只买不卖，或者大幅上涨才卖
            decision = '网格做多 📈'
            reason = '上涨趋势中，采用趋势策略'
        elif trend == 'down':
            # 下跌趋势：只卖不买，或者超跌才买
            decision = '观望等待 📉'
            reason = '下跌趋势中，暂时不做网格'
        else:
            # 震荡：正常网格
            decision = '网格交易 ➡️'
            reason = '震荡行情，适合网格'
        
        return {
            'trend': trend,
            'trend_signal': trend_signal,
            'grids': grids,
            'decision': decision,
            'reason': reason
        }


if __name__ == "__main__":
    print("✅ 网格交易策略已加载")
    print("\n策略说明:")
    print("  - 基础网格: 在震荡区间低买高卖")
    print("  - 趋势增强: 结合MA判断趋势，过滤逆势交易")
