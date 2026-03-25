#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时风控监控系统 v3.0
三层风控体系 + 动态调整
"""
import os
import sys
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

# 导入数据源
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_fetcher import get_stock_realtime


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Position:
    code: str
    name: str
    shares: int
    cost: float
    price: float = 0
    
    @property
    def market_value(self) -> float:
        return self.price * self.shares
    
    @property
    def pnl(self) -> float:
        return (self.price - self.cost) * self.shares
    
    @property
    def pnl_pct(self) -> float:
        return (self.price - self.cost) / self.cost if self.cost > 0 else 0


@dataclass
class RiskCheckResult:
    passed: bool
    risk_level: RiskLevel
    alerts: List[Dict] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    message: str = ""


class RealTimeRiskMonitor:
    """实时风控监控器"""
    
    def __init__(self):
        # 事前风控参数
        self.pre_trade = {
            "max_single_position": 0.20,    # 单标的上限 20%
            "stop_loss": -0.08,             # 止损线 -8%
            "min_cash_ratio": 0.10,         # 最低现金比例 10%
        }
        
        # 事中风控参数
        self.intra_trade = {
            "price_change_threshold": 0.05,  # 价格波动阈值 5%
            "trailing_stop": 0.15,          # 跟踪止盈 15%
            "trailing_start": 0.20,         # 跟踪止盈启动 20%
        }
        
        # 事后风控参数
        self.post_trade = {
            "max_drawdown": -0.15,          # 最大回撤 -15%
            "max_daily_loss": -0.05,        # 单日最大亏损 -5%
            "max_positions": 10,           # 最大持仓数量
        }
        
        # 状态
        self.positions: Dict[str, Position] = {}
        self.total_value = 0
        self.cash = 0
        self.peak_value = 0
        self.initial_capital = 0
        self.alert_history: List[Dict] = []
        self.monitoring = False
    
    def pre_trade_check(self, action: str, symbol: str, shares: int, price: float) -> RiskCheckResult:
        """事前风控检查"""
        alerts = []
        actions = []
        risk_level = RiskLevel.LOW
        passed = True
        
        trade_value = shares * price
        trade_ratio = trade_value / self.total_value if self.total_value > 0 else 0
        
        if action == "buy":
            # 仓位检查
            current_pos = self.positions.get(symbol, Position(symbol, "", 0, 0, price))
            new_weight = (current_pos.market_value + trade_value) / self.total_value
            
            if new_weight > self.pre_trade["max_single_position"]:
                passed = False
                risk_level = RiskLevel.HIGH
                alerts.append({"level": "error", "message": f"单票仓位超限: {new_weight:.1%}"})
                actions.append("拒绝买入")
            
            # 现金检查
            if trade_value > self.cash:
                passed = False
                risk_level = RiskLevel.HIGH
                alerts.append({"level": "error", "message": "现金不足"})
                actions.append("拒绝买入")
        
        # 止损检查
        if symbol in self.positions:
            pos = self.positions[symbol]
            if pos.pnl_pct <= self.pre_trade["stop_loss"]:
                passed = False
                risk_level = RiskLevel.CRITICAL
                alerts.append({"level": "critical", "message": f"触发止损: {pos.pnl_pct:.1%}"})
                actions.append("强制止损")
        
        return RiskCheckResult(passed, risk_level, alerts, actions, "事前风控" + ("通过" if passed else "未通过"))
    
    def intra_trade_monitor(self) -> RiskCheckResult:
        """事中风控监控"""
        alerts = []
        actions = []
        risk_level = RiskLevel.LOW
        passed = True
        
        total_pnl = 0
        
        for symbol, pos in self.positions.items():
            rt = get_stock_realtime(symbol)
            if rt:
                pos.price = rt.get("price", pos.price)
            
            pnl_pct = pos.pnl_pct
            
            # 止损
            if pnl_pct <= self.pre_trade["stop_loss"]:
                passed = False
                risk_level = RiskLevel.CRITICAL
                alerts.append({"level": "critical", "message": f"{symbol} 触发止损: {pnl_pct:.1%}"})
                actions.append(f"卖出 {symbol}")
            
            # 跟踪止盈
            elif pnl_pct >= self.intra_trade["trailing_start"]:
                alerts.append({"level": "warning", "message": f"{symbol} 跟踪止盈中"})
        
        # 组合熔断
        total_pnl_pct = total_pnl / self.initial_capital if self.initial_capital > 0 else 0
        if total_pnl_pct <= self.post_trade["max_daily_loss"]:
            passed = False
            risk_level = RiskLevel.CRITICAL
            alerts.append({"level": "critical", "message": f"组合熔断: {total_pnl_pct:.1%}"})
            actions.append("暂停所有交易")
        
        return RiskCheckResult(passed, risk_level, alerts, actions, "事中风控" + ("通过" if passed else "未通过"))
    
    def post_trade_analysis(self, positions: Dict) -> Dict:
        """事后风控分析"""
        wins = sum(1 for p in positions.values() if p.pnl > 0)
        losses = len(positions) - wins
        win_rate = wins / len(positions) if positions else 0
        
        report = {
            "timestamp": datetime.now(),
            "total_value": self.total_value,
            "positions": len(positions),
            "win_rate": win_rate,
            "recommendations": []
        }
        
        if win_rate < 0.4:
            report["recommendations"].append("优化选股策略")
        
        if len(positions) > self.post_trade["max_positions"]:
            report["recommendations"].append("减少持仓数量")
        
        return report
    
    def set_portfolio(self, positions: Dict, cash: float, initial_capital: float):
        """设置组合"""
        self.positions = positions
        self.cash = cash
        self.initial_capital = initial_capital
        self.total_value = cash + sum(p.market_value for p in positions.values())
        self.peak_value = self.total_value


# 测试
if __name__ == "__main__":
    print("╔════════════════════════════════╗")
    print("║ 实时风控监控系统 v3.0 测试 ║")
    print("╚════════════════════════════════╝")
    
    monitor = RealTimeRiskMonitor()
    
    # 设置模拟持仓
    positions = {
        "600519": Position("600519", "茅台", 100, 1500, 1426),
        "600036": Position("600036", "招商", 1000, 35, 39),
    }
    monitor.set_portfolio(positions, 50000, 200000)
    
    # 事前检查
    print("\n事前风控:")
    result = monitor.pre_trade_check("buy", "600519", 100, 1500)
    print(f"  {result.message}")
    
    # 事中监控
    print("\n事中风控:")
    result = monitor.intra_trade_monitor()
    print(f"  {result.message}")
    
    # 事后分析
    print("\n事后风控:")
    result = monitor.post_trade_analysis(positions)
    print(f"  胜率: {result['win_rate']:.1%}")
    
    print("\n✅ 测试完成")
