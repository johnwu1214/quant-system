#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纸上交易系统 (Paper Trading)
模拟真实交易环境，验证策略有效性
"""
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class PaperTradingSystem:
    """纸上交易系统"""
    
    def __init__(self, initial_capital: float = 100000):
        # 账户状态
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}  # {code: {'shares': int, 'cost': float}}
        self.total_commission = 0
        
        # 交易记录
        self.trades = []  # [{'date', 'code', 'action', 'shares', 'price', 'commission'}]
        self.daily_values = []  # 每日收盘市值
        
        # 交易参数
        self.commission_rate = 0.0003  # 万三手续费
        self.stamp_tax = 0.001  # 千一印花税 (卖出时)
        self.slippage = 0.001  # 0.1% 滑点
        
        # 数据存储
        self.data_dir = os.path.expanduser("~/quant_system/data/paper_trading")
        os.makedirs(self.data_dir, exist_ok=True)
        
        print(f"✅ 纸上交易系统初始化")
        print(f"   初始资金: ¥{initial_capital:,.0f}")
    
    def get_position_value(self, prices: Dict[str, float]) -> float:
        """获取持仓市值"""
        total = 0
        for code, pos in self.positions.items():
            price = prices.get(code, 0)
            total += price * pos['shares']
        return total
    
    def get_total_assets(self, prices: Dict[str, float]) -> float:
        """获取总资产"""
        return self.cash + self.get_position_value(prices)
    
    def can_buy(self, code: str, price: float, shares: int) -> bool:
        """检查是否可以买入"""
        cost = price * shares * (1 + self.commission_rate + self.slippage)
        return self.cash >= cost
    
    def can_sell(self, code: str, shares: int) -> bool:
        """检查是否可以卖出"""
        return code in self.positions and self.positions[code]['shares'] >= shares
    
    def buy(self, code: str, name: str, price: float, shares: int, date: str = None) -> Dict:
        """买入股票"""
        date = date or datetime.now().strftime("%Y-%m-%d")
        
        # 计算成本（含手续费和滑点）
        actual_price = price * (1 + self.slippage)  # 滑点
        commission = price * shares * self.commission_rate
        total_cost = price * shares + commission  # 用原始价格计算手续费
        
        if self.cash < total_cost:
            return {"success": False, "reason": "资金不足"}
        
        # 执行买入
        self.cash -= total_cost
        
        if code not in self.positions:
            self.positions[code] = {"name": name, "shares": 0, "cost": 0}
        
        # 更新持仓成本
        old_shares = self.positions[code]['shares']
        old_cost = self.positions[code]['cost'] * old_shares
        new_cost = old_cost + actual_price * shares
        self.positions[code]['shares'] = old_shares + shares
        self.positions[code]['cost'] = new_cost / self.positions[code]['shares']
        
        self.total_commission += commission
        
        # 记录交易
        trade = {
            "date": date,
            "code": code,
            "name": name,
            "action": "BUY",
            "price": actual_price,
            "shares": shares,
            "commission": commission,
            "total": total_cost
        }
        self.trades.append(trade)
        
        return {"success": True, "trade": trade}
    
    def sell(self, code: str, name: str, price: float, shares: int, date: str = None) -> Dict:
        """卖出股票"""
        date = date or datetime.now().strftime("%Y-%m-%d")
        
        if code not in self.positions or self.positions[code]['shares'] < shares:
            return {"success": False, "reason": "持仓不足"}
        
        # 计算收益（含手续费、印花税和滑点）
        commission = price * shares * self.commission_rate
        stamp_tax = price * shares * self.stamp_tax
        total_proceeds = price * shares - commission - stamp_tax
        
        # 更新持仓
        self.positions[code]['shares'] -= shares
        if self.positions[code]['shares'] <= 0:
            del self.positions[code]
        
        self.cash += total_proceeds
        self.total_commission += commission
        
        # 记录交易
        trade = {
            "date": date,
            "code": code,
            "name": name,
            "action": "SELL",
            "price": price,
            "shares": shares,
            "commission": commission,
            "total": total_proceeds
        }
        self.trades.append(trade)
        
        return {"success": True, "trade": trade}
    
    def update_daily(self, prices: Dict[str, float], date: str = None):
        """每日收盘更新"""
        date = date or datetime.now().strftime("%Y-%m-%d")
        
        total_value = self.get_total_assets(prices)
        
        self.daily_values.append({
            "date": date,
            "cash": self.cash,
            "position_value": self.get_position_value(prices),
            "total_value": total_value,
            "positions": {code: dict(pos) for code, pos in self.positions.items()}
        })
    
    def get_returns(self) -> Dict:
        """计算收益率"""
        if not self.daily_values:
            return {}
        
        initial = self.initial_capital
        current = self.daily_values[-1]['total_value']
        
        total_return = (current - initial) / initial
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t['action'] == 'SELL' and t['total'] > t['price'] * t['shares'])
        
        return {
            "initial_capital": initial,
            "current_value": current,
            "total_return": total_return,
            "total_return_pct": total_return * 100,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "win_rate": winning_trades / total_trades * 100 if total_trades > 0 else 0,
            "total_commission": self.total_commission
        }
    
    def generate_report(self, current_prices: Dict[str, float]) -> str:
        """生成交易报告"""
        returns = self.get_returns()
        
        report = f"""
📊 **纸上交易报告** - {datetime.now().strftime('%Y-%m-%d')}
{'='*50}

💰 **账户状态**
   初始资金: ¥{returns['initial_capital']:,.0f}
   当前资产: ¥{returns['current_value']:,.0f}
   总收益率: {returns['total_return_pct']:+.2f}%
   持仓市值: ¥{self.get_position_value(current_prices):,.0f}
   可用现金: ¥{self.cash:,.0f}

{'='*50}
📈 **持仓明细**
"""
        
        for code, pos in self.positions.items():
            price = current_prices.get(code, 0)
            cost = pos['cost']
            shares = pos['shares']
            value = price * shares
            pl = (price - cost) * shares
            pl_pct = (price - cost) / cost * 100 if cost > 0 else 0
            
            emoji = "🟢" if pl >= 0 else "🔴"
            report += f"\n{emoji} {pos['name']} ({code}):\n"
            report += f"   持仓: {shares}股 | 成本: ¥{cost:.2f} | 当前: ¥{price:.2f}\n"
            report += f"   盈亏: {pl:+,.0f}元 ({pl_pct:+.1f}%)\n"
        
        report += f"""
{'='*50}
📋 **交易统计**
   总交易次数: {returns['total_trades']}
   盈利次数: {returns['winning_trades']}
   胜率: {returns['win_rate']:.1f}%
   手续费: ¥{returns['total_commission']:,.2f}

{'='*50}
"""
        
        return report
    
    def save_state(self):
        """保存状态"""
        state = {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "positions": self.positions,
            "trades": self.trades,
            "daily_values": self.daily_values,
            "total_commission": self.total_commission
        }
        
        filepath = os.path.join(self.data_dir, "state.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 状态已保存: {filepath}")
    
    def load_state(self):
        """加载状态"""
        filepath = os.path.join(self.data_dir, "state.json")
        if not os.path.exists(filepath):
            return False
        
        with open(filepath, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        self.initial_capital = state['initial_capital']
        self.cash = state['cash']
        self.positions = state['positions']
        self.trades = state['trades']
        self.daily_values = state['daily_values']
        self.total_commission = state['total_commission']
        
        print(f"✅ 状态已加载")
        return True
    
    def reset(self):
        """重置系统"""
        self.cash = self.initial_capital
        self.positions = {}
        self.trades = []
        self.daily_values = []
        self.total_commission = 0
        print("✅ 系统已重置")


# 测试
if __name__ == "__main__":
    print("🧪 测试纸上交易系统...")
    
    # 创建系统
    paper = PaperTradingSystem(100000)
    
    # 模拟交易
    print("\n📈 模拟交易:")
    
    # 买入
    result = paper.buy("600519", "贵州茅台", 1500, 100, "2025-01-15")
    print(f"买入茅台: {'成功' if result['success'] else '失败'}")
    
    # 卖出
    result = paper.sell("600519", "贵州茅台", 1600, 50, "2025-02-15")
    print(f"卖出茅台: {'成功' if result['success'] else '失败'}")
    
    # 更新每日
    paper.update_daily({"600519": 1600}, "2025-02-15")
    
    # 生成报告
    report = paper.get_returns()
    print(f"\n📊 收益:")
    print(f"   初始: ¥{report['initial_capital']:,.0f}")
    print(f"   当前: ¥{report['current_value']:,.0f}")
    print(f"   收益率: {report['total_return_pct']:+.2f}%")
    
    print("\n✅ 测试完成")
