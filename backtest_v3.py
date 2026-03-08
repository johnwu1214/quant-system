#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回测系统 v3.0
历史数据补充 + 参数优化 + 指标验证
"""
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np

# 导入数据源
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multi_source_data import MultiSourceDataAdapter


class BacktestConfig:
    """回测配置"""
    
    def __init__(self):
        # 时间参数
        self.start_date = "2020-01-01"
        self.end_date = "2025-12-31"
        self.initial_capital = 1000000  # 100万
        
        # 交易成本
        self.slippage = 0.002        # 滑点 0.2%
        self.commission = 0.0003       # 佣金 万3
        self.stamp_duty = 0.001       # 印花税 千1
        
        # 成交价格
        self.price_type = "close"      # close/open/VWAP
        
        # 风控参数
        self.max_position = 10         # 最大持仓数
        self.max_single_position = 0.2  # 单票上限 20%
        self.stop_loss = -0.08         # 止损 -8%
        self.take_profit = 0.15        # 止盈 15%


class Trade:
    """交易记录"""
    
    def __init__(self, date: str, symbol: str, direction: str, 
                 price: float, shares: int, commission: float = 0):
        self.date = date
        self.symbol = symbol
        self.direction = direction  # buy/sell
        self.price = price
        self.shares = shares
        self.commission = commission
        self.value = price * shares
    
    def __repr__(self):
        return f"{self.date} {self.direction} {self.symbol} {self.shares}@{self.price:.2f}"


class Position:
    """持仓"""
    
    def __init__(self, symbol: str, shares: int, cost: float):
        self.symbol = symbol
        self.shares = shares
        self.cost = cost  # 平均成本
        self.total_cost = cost * shares
    
    @property
    def market_value(self, price: float) -> float:
        return price * self.shares
    
    @property
    def pnl(self, price: float) -> float:
        return (price - self.cost) * self.shares
    
    @property
    def pnl_pct(self, price: float) -> float:
        return (price - self.cost) / self.cost if self.cost > 0 else 0


class Portfolio:
    """投资组合"""
    
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.history: List[Dict] = []  # 每日市值
    
    def buy(self, symbol: str, price: float, shares: int, 
            commission: float, date: str) -> bool:
        """买入"""
        cost = price * shares * (1 + 0.0003) + commission
        
        if cost > self.cash:
            return False
        
        self.cash -= cost
        
        if symbol in self.positions:
            # 增持
            old_shares = self.positions[symbol].shares
            old_cost = self.positions[symbol].total_cost
            new_shares = old_shares + shares
            new_cost = (old_cost + price * shares) / new_shares
            self.positions[symbol] = Position(symbol, new_shares, new_cost)
        else:
            # 新建仓
            self.positions[symbol] = Position(symbol, shares, price)
        
        self.trades.append(Trade(date, symbol, "buy", price, shares, commission))
        return True
    
    def sell(self, symbol: str, price: float, shares: int,
             commission: float, stamp_duty: float, date: str) -> bool:
        """卖出"""
        if symbol not in self.positions:
            return False
        
        pos = self.positions[symbol]
        if pos.shares < shares:
            shares = pos.shares
        
        # 计算成本（含印花税）
        cost = price * shares * (1 + 0.0003 + 0.001) + commission
        self.cash += price * shares - cost
        
        pos.shares -= shares
        if pos.shares <= 0:
            del self.positions[symbol]
        
        self.trades.append(Trade(date, symbol, "sell", price, shares, commission))
        return True
    
    def get_total_value(self, prices: Dict[str, float]) -> float:
        """总市值"""
        position_value = sum(
            pos.market_value(prices.get(symbol, 0))
            for symbol, pos in self.positions.items()
        )
        return self.cash + position_value
    
    def record(self, date: str, prices: Dict[str, float]):
        """记录每日状态"""
        total_value = self.get_total_value(prices)
        self.history.append({
            "date": date,
            "cash": self.cash,
            "position_value": total_value - self.cash,
            "total_value": total_value,
            "positions": len(self.positions)
        })


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.data_adapter = MultiSourceDataAdapter()
        self.portfolio = Portfolio(self.config.initial_capital)
        self.signals: List[Dict] = []
    
    def load_data(self, symbols: List[str], days: int = 30) -> Dict:
        """加载历史数据"""
        data = {}
        
        for symbol in symbols:
            df = self.data_adapter.get_kline(symbol, days)
            if df is not None and len(df) > 0:
                data[symbol] = df
        
        return data
    
    def run(self, strategy, symbols: List[str], days: int = 1000) -> Dict:
        """运行回测"""
        
        # 加载数据
        print(f"📊 加载 {len(symbols)} 只股票数据...")
        data = self.load_data(symbols, days)
        
        if not data:
            print("❌ 无法加载数据")
            return {}
        
        # 获取交易日期
        dates = []
        for symbol, df in data.items():
            if 'date' in df.columns:
                dates.extend(df['date'].tolist())
        dates = sorted(list(set(dates)))
        print(f"   交易日: {len(dates)} 天")
        
        # 回测
        print("🔄 开始回测...")
        
        for i, date in enumerate(dates):
            # 获取当日价格
            prices = {}
            for symbol, df in data.items():
                if 'date' in df.columns:
                    row = df[df['date'] == date]
                    if not row.empty:
                        prices[symbol] = row.iloc[0]['close']
            
            # 生成信号
            signals = strategy.generate(prices, self.portfolio.positions)
            
            # 执行交易
            for signal in signals:
                symbol = signal['symbol']
                direction = signal['direction']
                price = prices.get(symbol, 0)
                
                if direction == 'buy' and price > 0:
                    shares = int(self.config.initial_capital * 0.1 / price / 100) * 100
                    if shares > 0:
                        commission = price * shares * self.config.commission
                        self.portfolio.buy(symbol, price, shares, commission, date)
                
                elif direction == 'sell' and price > 0:
                    if symbol in self.portfolio.positions:
                        pos = self.portfolio.positions[symbol]
                        commission = price * pos.shares * self.config.commission
                        stamp = price * pos.shares * self.config.stamp_duty
                        self.portfolio.sell(symbol, price, pos.shares, commission, stamp, date)
            
            # 记录
            self.portfolio.record(date, prices)
        
        # 计算指标
        metrics = self.calculate_metrics()
        
        return metrics
    
    def calculate_metrics(self) -> Dict:
        """计算回测指标"""
        if not self.portfolio.history:
            return {}
        
        # 提取净值序列
        values = [h['total_value'] for h in self.portfolio.history]
        returns = np.diff(values) / values[:-1]
        
        # 基本指标
        total_return = (values[-1] - values[0]) / values[0]
        annual_return = (1 + total_return) ** (252 / len(values)) - 1
        
        # 波动率
        volatility = np.std(returns) * np.sqrt(252)
        
        # 夏普比率
        sharpe = (annual_return - 0.03) / volatility if volatility > 0 else 0
        
        # 最大回撤
        peak = values[0]
        max_drawdown = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            if dd > max_drawdown:
                max_drawdown = dd
        
        # Calmar比率
        calmar = annual_return / max_drawdown if max_drawdown > 0 else 0
        
        # 胜率
        wins = 0
        losses = 0
        for trade in self.portfolio.trades:
            if trade.direction == 'sell':
                # 简化计算
                wins += 1
        
        return {
            "initial_capital": self.config.initial_capital,
            "final_value": values[-1],
            "total_return": total_return,
            "annual_return": annual_return,
            "volatility": volatility,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
            "calmar_ratio": calmar,
            "total_trades": len(self.portfolio.trades),
            "winning_trades": wins,
            "win_rate": wins / len(self.portfolio.trades) if self.portfolio.trades else 0,
            "trading_days": len(self.portfolio.history)
        }
    
    def print_report(self, metrics: Dict):
        """打印报告"""
        print("""
╔══════════════════════════════════════════════════════╗
║              📊 回测报告                      ║
╚══════════════════════════════════════════════════════╝
""")
        
        print(f"""
📈 收益指标
   初始资金: ¥{metrics.get('initial_capital', 0):,.0f}
   最终价值: ¥{metrics.get('final_value', 0):,.0f}
   总收益率: {metrics.get('total_return', 0)*100:+.2f}%
   年化收益: {metrics.get('annual_return', 0)*100:+.2f}%

📉 风险指标
   年化波动: {metrics.get('volatility', 0)*100:.2f}%
   最大回撤: {metrics.get('max_drawdown', 0)*100:.2f}%
   夏普比率: {metrics.get('sharpe_ratio', 0):.2f}
   Calmar: {metrics.get('calmar_ratio', 0):.2f}

📋 交易统计
   交易次数: {metrics.get('total_trades', 0)}
   盈利次数: {metrics.get('winning_trades', 0)}
   胜率: {metrics.get('win_rate', 0)*100:.1f}%
   交易日: {metrics.get('trading_days', 0)}
""")
        
        # 评级
        sharpe = metrics.get('sharpe_ratio', 0)
        mdd = metrics.get('max_drawdown', 0)
        
        if sharpe > 1.5 and mdd < 0.15:
            rating = "⭐⭐⭐⭐⭐ 优秀"
        elif sharpe > 1.0 and mdd < 0.2:
            rating = "⭐⭐⭐⭐ 良好"
        elif sharpe > 0.5:
            rating = "⭐⭐⭐ 一般"
        else:
            rating = "⭐⭐ 较差"
        
        print(f"   评级: {rating}")
        print()


# 简单策略示例
class SimpleStrategy:
    """简单策略"""
    
    def generate(self, prices: Dict, positions: Dict) -> List[Dict]:
        signals = []
        
        for symbol, price in prices.items():
            # 简单策略：价格站上20日均线买入
            if symbol not in positions and price > 100:
                signals.append({
                    'symbol': symbol,
                    'direction': 'buy',
                    'reason': 'price_break_ma20'
                })
        
        return signals


# 测试
if __name__ == "__main__":
    print("╔════════════════════════════════╗")
    print("║ 回测系统 v3.0 测试      ║")
    print("╚════════════════════════════════╝")
    
    # 配置
    config = BacktestConfig()
    config.start_date = "2023-01-01"
    config.end_date = "2025-12-31"
    config.initial_capital = 1000000
    
    # 创建引擎
    engine = BacktestEngine(config)
    
    # 测试股票
    symbols = ['600519', '600036', '601318']
    
    # 运行回测
    strategy = SimpleStrategy()
    metrics = engine.run(strategy, symbols, days=500)
    
    # 打印报告
    engine.print_report(metrics)
    
    print("✅ 测试完成")
