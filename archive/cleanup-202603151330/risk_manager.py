#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版风控系统
事前/事中/事后 全流程风控
"""
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class RiskManager:
    """风控管理器"""
    
    def __init__(self):
        # 风控参数配置
        self.config = {
            # 仓位控制
            "max_position_single": 0.30,  # 单只股票最大仓位30%
            "max_position_total": 0.90,  # 总仓位上限90%
            "min_cash_reserve": 0.10,    # 最低现金储备10%
            
            # 止损止盈
            "stop_loss": -0.08,          # 默认止损8%
            "stop_loss_wave": -0.05,     # 波动止损5%
            "take_profit": 0.15,         # 默认止盈15%
            "take_profit_trail": 0.10,   # 追踪止盈10%
            
            # 风险控制
            "max_daily_loss": -0.05,     # 单日最大亏损5%
            "max_drawdown": -0.15,       # 最大回撤15%
            "max_concentration": 0.50,   # 最大集中度50%
            
            # 交易控制
            "max_trades_per_day": 10,   # 每日最大交易次数
            "min_trade_interval": 300,  # 最小交易间隔(秒)
            "max_order_size": 10000,     # 单笔最大订单金额
        }
        
        # 状态
        self.daily_trades = 0
        self.last_trade_time = None
        self.positions = {}
        self.daily_pnl = 0
        self.peak_value = 0
        self.init_capital = 0
    
    def set_config(self, key: str, value):
        """设置风控参数"""
        if key in self.config:
            self.config[key] = value
    
    def set_positions(self, positions: Dict):
        """设置当前持仓"""
        self.positions = positions
    
    def set_capital(self, capital: float):
        """设置初始资金"""
        self.init_capital = capital
        self.peak_value = capital
    
    # ==================== 事前风控 ====================
    
    def pre_check(self, action: str, stock_code: str, 
                  price: float, shares: int = 0, amount: float = 0) -> Dict:
        """
        事前风控检查
        返回: {"approved": bool, "reason": str, "adjustments": dict}
        """
        result = {
            "approved": True,
            "reason": "通过",
            "adjustments": {},
            "warnings": []
        }
        
        # 计算交易金额
        trade_amount = amount if amount > 0 else price * shares
        total_value = sum(p.get("market_value", 0) for p in self.positions.values())
        total_value += trade_amount if action == "buy" else 0
        
        # 1. 检查总仓位
        if self.init_capital > 0:
            position_ratio = total_value / self.init_capital
            if position_ratio > self.config["max_position_total"]:
                result["approved"] = False
                result["reason"] = f"总仓位超限: {position_ratio:.1%} > {self.config['max_position_total']:.1%}"
                return result
            
            if position_ratio > self.config["max_position_total"] * 0.9:
                result["warnings"].append(f"总仓位较高: {position_ratio:.1%}")
        
        # 2. 检查单票仓位
        if action == "buy":
            current_position = self.positions.get(stock_code, {}).get("market_value", 0)
            new_position = current_position + trade_amount
            
            if self.init_capital > 0:
                single_ratio = new_position / self.init_capital
                if single_ratio > self.config["max_position_single"]:
                    # 自动调整
                    max_amount = self.config["max_position_single"] * self.init_capital - current_position
                    if max_amount > 0:
                        result["adjustments"]["shares"] = int(max_amount / price)
                        result["adjustments"]["amount"] = max_amount
                        result["warnings"].append(f"单票仓位超限，自动调整为{result['adjustments']['shares']}股")
                    else:
                        result["approved"] = False
                        result["reason"] = f"单票仓位已满"
                        return result
        
        # 3. 检查现金储备
        if action == "buy":
            current_cash = self.init_capital - total_value
            if current_cash < self.config["min_cash_reserve"] * self.init_capital:
                result["approved"] = False
                result["reason"] = "现金储备不足"
                return result
        
        # 4. 检查交易次数
        if self.daily_trades >= self.config["max_trades_per_day"]:
            result["approved"] = False
            result["reason"] = f"今日交易次数已达上限: {self.daily_trades}"
            return result
        
        # 5. 检查最小交易间隔
        if self.last_trade_time:
            elapsed = (datetime.now() - self.last_trade_time).seconds
            if elapsed < self.config["min_trade_interval"]:
                result["approved"] = False
                result["reason"] = f"交易间隔不足: {elapsed}秒 < {self.config['min_trade_interval']}秒"
                return result
        
        # 6. 检查单笔金额
        if trade_amount > self.config["max_order_size"]:
            result["warnings"].append(f"单笔金额较大: ¥{trade_amount:,.0f}")
        
        # 7. 检查涨跌停
        # (需要实时行情数据，此处略)
        
        return result
    
    # ==================== 事中风控 ====================
    
    def monitor_position(self, stock_code: str, current_price: float, 
                        cost: float, shares: int) -> Dict:
        """
        事中持仓监控
        返回风控信号
        """
        pnl_pct = (current_price - cost) / cost if cost > 0 else 0
        
        signals = {
            "code": stock_code,
            "price": current_price,
            "cost": cost,
            "pnl_pct": pnl_pct,
            "actions": [],
            "level": "normal"  # normal, warning, critical
        }
        
        # 1. 止损检查
        if pnl_pct <= self.config["stop_loss"]:
            signals["actions"].append({
                "action": "止损",
                "priority": "high",
                "reason": f"触发止损: {pnl_pct:.1%}"
            })
            signals["level"] = "critical"
        
        # 2. 止盈检查
        if pnl_pct >= self.config["take_profit"]:
            signals["actions"].append({
                "action": "止盈",
                "priority": "medium",
                "reason": f"触发止盈: {pnl_pct:.1%}"
            })
            if signals["level"] != "critical":
                signals["level"] = "warning"
        
        # 3. 回撤检查
        if self.init_capital > 0:
            current_value = current_price * shares
            total_value = sum(p.get("market_value", 0) for p in self.positions.values()) + current_value
            drawdown = (total_value - self.peak_value) / self.peak_value
            
            if drawdown <= self.config["max_drawdown"]:
                signals["actions"].append({
                    "action": "减仓",
                    "priority": "high",
                    "reason": f"触发最大回撤: {drawdown:.1%}"
                })
                signals["level"] = "critical"
        
        # 4. 波动止损（追踪）
        if pnl_pct <= self.config["stop_loss_wave"]:
            signals["actions"].append({
                "action": "波动止损",
                "priority": "medium",
                "reason": f"波动超限: {pnl_pct:.1%}"
            })
            if signals["level"] == "normal":
                signals["level"] = "warning"
        
        # 5. 风险提示
        if pnl_pct <= -0.05 and signals["level"] == "normal":
            signals["warnings"] = [f"浮亏较大: {pnl_pct:.1%}"]
            signals["level"] = "warning"
        
        return signals
    
    # ==================== 事后风控 ====================
    
    def post_trade_check(self, action: str, stock_code: str, 
                         price: float, shares: int) -> Dict:
        """事后交易检查"""
        result = {
            "action": action,
            "code": stock_code,
            "price": price,
            "shares": shares,
            "amount": price * shares,
            "approved": True,
            "issues": []
        }
        
        # 更新交易计数
        self.daily_trades += 1
        self.last_trade_time = datetime.now()
        
        # 更新持仓
        if action == "buy":
            if stock_code not in self.positions:
                self.positions[stock_code] = {"shares": 0, "cost": 0}
            self.positions[stock_code]["shares"] += shares
            self.positions[stock_code]["cost"] = (
                self.positions[stock_code]["cost"] + price * shares
            ) / self.positions[stock_code]["shares"] if self.positions[stock_code]["shares"] > 0 else 0
        
        elif action == "sell":
            if stock_code in self.positions:
                self.positions[stock_code]["shares"] -= shares
                if self.positions[stock_code]["shares"] <= 0:
                    del self.positions[stock_code]
        
        # 检查是否需要平仓
        if self.daily_trades >= self.config["max_trades_per_day"]:
            result["issues"].append("达到每日交易上限")
        
        return result
    
    def end_of_day(self, total_value: float) -> Dict:
        """日终风控检查"""
        result = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_value": total_value,
            "daily_pnl": total_value - self.init_capital,
            "daily_pnl_pct": (total_value - self.init_capital) / self.init_capital if self.init_capital > 0 else 0,
            "drawdown": 0,
            "issues": [],
            "actions": []
        }
        
        # 计算回撤
        if self.init_capital > 0:
            result["drawdown"] = (total_value - self.peak_value) / self.peak_value
        
        # 更新峰值
        if total_value > self.peak_value:
            self.peak_value = total_value
        
        # 检查日亏损
        if result["daily_pnl_pct"] <= self.config["max_daily_loss"]:
            result["issues"].append(f"日亏损超限: {result['daily_pnl_pct']:.1%}")
            result["actions"].append("次日暂停交易")
        
        # 检查回撤
        if result["drawdown"] <= self.config["max_drawdown"]:
            result["issues"].append(f"回撤超限: {result['drawdown']:.1%}")
            result["actions"].append("启动减仓策略")
        
        # 重置每日计数
        self.daily_trades = 0
        
        return result
    
    # ==================== 风险报告 ====================
    
    def generate_risk_report(self, positions: Dict, total_value: float) -> str:
        """生成风控报告"""
        report = f"""
🛡️ **风控日报** - {datetime.now().strftime('%Y-%m-%d %H:%M')}
{'='*50}

📊 **账户状态**
   总资产: ¥{total_value:,.0f}
   持仓数量: {len(positions)}只
   持仓占比: {total_value/self.init_capital*100:.1f}% (上限90%)
   现金储备: ¥{self.init_capital - total_value:,.0f}
"""
        
        # 持仓风控
        report += f"""
{'='*50}
📈 **持仓风控**
"""
        for code, pos in positions.items():
            price = pos.get("price", 0)
            cost = pos.get("cost", 0)
            shares = pos.get("shares", 0)
            
            if cost > 0 and price > 0:
                pnl_pct = (price - cost) / cost * 100
                emoji = "🟢" if pnl_pct > 0 else "🔴"
                
                # 检查是否触发风控
                alerts = []
                if pnl_pct <= self.config["stop_loss"] * 100:
                    alerts.append("⚠️ 触发止损")
                if pnl_pct >= self.config["take_profit"] * 100:
                    alerts.append("🎯 触发止盈")
                
                alert_str = " ".join(alerts) if alerts else ""
                
                report += f"{emoji} {pos.get('name', code)}: ¥{price:.2f} ({pnl_pct:+.1f}%) {alert_str}\n"
        
        # 风险提示
        report += f"""
{'='*50}
⚠️ **风控参数**
   止损线: {self.config['stop_loss']*100:.0f}%
   止盈线: {self.config['take_profit']*100:.0f}%
   最大回撤: {self.config['max_drawdown']*100:.0f}%
   单票上限: {self.config['max_position_single']*100:.0f}%
   今日交易: {self.daily_trades}/{self.config['max_trades_per_day']}
{'='*50}
🦞 风控系统自动监控
"""
        
        return report


# 测试
if __name__ == "__main__":
    print("🧪 测试风控系统...")
    
    rm = RiskManager()
    rm.set_capital(100000)
    
    # 模拟持仓
    rm.set_positions({
        "600519": {"name": "贵州茅台", "shares": 100, "cost": 1800, "market_value": 190000}
    })
    
    # 测试事前风控
    print("\n📋 事前风控检查...")
    result = rm.pre_check("buy", "000001", price=10, shares=1000)
    print(f"   结果: {result['approved']} - {result['reason']}")
    
    # 测试事中监控
    print("\n📡 事中持仓监控...")
    signal = rm.monitor_position("600519", current_price=1700, cost=1800, shares=100)
    print(f"   信号: {signal['level']} - 动作: {[a['action'] for a in signal['actions']]}")
    
    # 测试报告
    print("\n📊 生成风控报告...")
    report = rm.generate_risk_report({"600519": {"name": "贵州茅台", "price": 1700, "cost": 1800, "shares": 100}}, 190000)
    print(report)
    
    print("✅ 风控系统测试完成")
