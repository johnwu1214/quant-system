#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版风控系统 v2.0
三层风控架构 + 动态跟踪止盈
"""
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class EnhancedRiskManager:
    """增强版风控管理器"""
    
    def __init__(self):
        # ========== 风控参数配置 ==========
        
        # 第一层：账户级风控
        self.account_config = {
            "max_position_ratio": 0.85,      # 最大仓位 85%
            "min_cash_ratio": 0.15,          # 最低现金储备 15%
            "max_daily_loss": 0.05,          # 单日最大亏损 5%
            "max_drawdown": 0.15,           # 最大回撤 15%
        }
        
        # 第二层：业务级风控（单股）
        self.position_config = {
            "max_single_position": 0.20,     # 单只股票最大仓位 20%
            "stop_loss": -0.08,              # 固定止损 -8%
            "stop_loss_strict": -0.05,       # 严格止损 -5%（盈利后）
            "take_profit": 0.15,             # 止盈 15%
            "trailing_stop": 0.15,           # 跟踪止盈回撤 15%
            "trailing_start": 0.20,          # 跟踪止盈启动线 20%
            "max_holding_days": 30,          # 最大持仓天数
        }
        
        # 第三层：市场级风控
        self.market_config = {
            "index_drop_threshold": -0.03,   # 大盘跌幅 >3%
            "volatility_threshold": 30,       # VIX > 30
            "circuit_break": -0.05,           # 熔断阈值 -5%
        }
        
        # 状态
        self.positions = {}
        self.daily_pnl = 0
        self.peak_value = 0
        self.init_capital = 0
        self.highest_prices = {}  # 记录最高价（用于跟踪止盈）
    
    def set_capital(self, capital: float):
        """设置初始资金"""
        self.init_capital = capital
        self.peak_value = capital
    
    def set_positions(self, positions: Dict):
        """设置当前持仓"""
        self.positions = positions
        # 初始化最高价
        for code, pos in positions.items():
            if 'price' in pos:
                self.highest_prices[code] = pos['price']
    
    # ========== 第一层：账户级风控 ==========
    
    def check_account_risk(self, total_value: float, pos_value: float = None) -> Dict:
        """账户级风控检查
        total_value: 总资产
        pos_value: 持仓市值（可选），不传则从 positions 自动计算
        """
        result = {
            "level": "account",
            "approved": True,
            "actions": [],
            "warnings": []
        }
        
        if self.init_capital == 0 or total_value == 0:
            return result
        
        # 计算仓位比例（持仓市值/总资产）
        if pos_value is None:
            pos_value = sum(
                p.get('shares', 0) * p.get('current_price', p.get('cost', 0))
                for p in self.positions.values()
            ) if self.positions else 0
        position_ratio = pos_value / total_value
        
        # 检查仓位上限
        if position_ratio > self.account_config["max_position_ratio"]:
            result["approved"] = False
            result["actions"].append({
                "action": "强制平仓",
                "target": "50%",
                "reason": f"仓位超限: {position_ratio:.1%}"
            })
        elif position_ratio > self.account_config["max_position_ratio"] * 0.9:
            result["warnings"].append(f"仓位较高: {position_ratio:.1%}")
        
        # 检查现金储备
        cash_ratio = 1 - position_ratio
        if cash_ratio < self.account_config["min_cash_ratio"]:
            result["warnings"].append(f"现金储备不足: {cash_ratio:.1%}")
        
        # 检查回撤
        drawdown = (total_value - self.peak_value) / self.peak_value if self.peak_value > 0 else 0
        if drawdown <= -self.account_config["max_drawdown"]:
            result["approved"] = False
            result["actions"].append({
                "action": "暂停交易",
                "reason": f"触发最大回撤: {drawdown:.1%}"
            })
        
        # 更新峰值
        if total_value > self.peak_value:
            self.peak_value = total_value
        
        return result
    
    # ========== 第二层：业务级风控 ==========
    
    def check_position_risk(self, code: str, current_price: float, 
                          cost_price: float, shares: int,
                          holding_days: int = 0) -> Dict:
        """单股票风控检查"""
        
        result = {
            "code": code,
            "level": "position",
            "approved": True,
            "actions": []
        }
        
        if cost_price == 0 or shares == 0:
            return result
        
        # 计算盈亏
        profit_pct = (current_price - cost_price) / cost_price
        profit_value = (current_price - cost_price) * shares
        
        # 更新最高价
        if code not in self.highest_prices:
            self.highest_prices[code] = current_price
        if current_price > self.highest_prices[code]:
            self.highest_prices[code] = current_price
        
        # 1. 固定止损检查
        if profit_pct <= self.position_config["stop_loss"]:
            result["actions"].append({
                "type": "STOP_LOSS",
                "action": "止损",
                "reason": f"触发固定止损: {profit_pct:.1%}",
                "priority": "HIGH"
            })
        
        # 2. 跟踪止盈检查（盈利>20%后）
        elif profit_pct >= self.position_config["trailing_start"]:
            highest = self.highest_prices[code]
            trailing_stop_price = highest * (1 - self.position_config["trailing_stop"])
            
            if current_price <= trailing_stop_price:
                result["actions"].append({
                    "type": "TRAILING_STOP",
                    "action": "跟踪止盈",
                    "reason": f"从最高价回撤{self.position_config['trailing_stop']*100:.0f}%",
                    "highest_price": highest,
                    "stop_price": trailing_stop_price,
                    "priority": "MEDIUM"
                })
        
        # 3. 持仓天数检查
        if holding_days > self.position_config["max_holding_days"]:
            result["actions"].append({
                "type": "TIME_EXIT",
                "action": "超时退出",
                "reason": f"持仓超过{holding_days}天",
                "priority": "LOW"
            })
        
        # 4. 严重亏损警告
        if profit_pct <= -self.position_config["stop_loss_strict"]:
            result["approved"] = False
        
        return result
    
    # ========== 第三层：市场级风控 ==========
    
    def check_market_risk(self, index_change: float = 0) -> Dict:
        """市场级风控检查"""
        
        result = {
            "level": "market",
            "approved": True,
            "actions": []
        }
        
        # 检查大盘跌幅
        if index_change <= self.market_config["circuit_break"]:
            result["approved"] = False
            result["actions"].append({
                "action": "清仓",
                "reason": f"大盘触发熔断: {index_change:.1%}"
            })
        elif index_change <= self.market_config["index_drop_threshold"]:
            result["actions"].append({
                "action": "减仓",
                "reason": f"大盘跌幅较大: {index_change:.1%}"
            })
        
        return result
    
    # ========== 综合风控检查 ==========
    
    def comprehensive_check(self, positions: Dict, total_value: float, 
                          index_change: float = 0) -> Dict:
        """综合风控检查"""
        
        report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_value": total_value,
            "account_risk": self.check_account_risk(total_value),
            "position_risks": [],
            "market_risk": self.check_market_risk(index_change),
            "urgent_actions": []
        }
        
        # 检查每个持仓
        for code, pos in positions.items():
            price = pos.get('price', 0)
            cost = pos.get('cost', 0)
            shares = pos.get('shares', 0)
            days = pos.get('holding_days', 0)
            
            if price > 0 and cost > 0:
                pos_risk = self.check_position_risk(code, price, cost, shares, days)
                report["position_risks"].append(pos_risk)
                
                # 收集紧急动作
                for action in pos_risk.get("actions", []):
                    if action.get("priority") == "HIGH":
                        report["urgent_actions"].append({
                            "code": code,
                            **action
                        })
        
        # 判断是否通过
        account_ok = report["account_risk"]["approved"]
        market_ok = report["market_risk"]["approved"]
        report["approved"] = account_ok and market_ok
        
        return report
    
    # ========== 风控报告 ==========
    
    def generate_report(self, positions: Dict, total_value: float) -> str:
        """生成风控报告"""
        
        report = self.comprehensive_check(positions, total_value)
        
        output = f"""
🛡️ **风控日报 v2.0** - {report['timestamp']}
{'='*50}

📊 **账户状态**
   总资产: ¥{total_value:,.0f}
   持仓数量: {len(positions)}只
   仓位比例: {total_value/self.init_capital*100:.1f}%
   最高峰值: ¥{self.peak_value:,.0f}
   回撤: {(total_value-self.peak_value)/self.peak_value*100:.1f}%

{'='*50}
📈 **持仓风控**
"""
        
        for code, pos in positions.items():
            price = pos.get('price', 0)
            cost = pos.get('cost', 0)
            name = pos.get('name', code)
            
            if price > 0 and cost > 0:
                profit_pct = (price - cost) / cost * 100
                emoji = "🟢" if profit_pct > 0 else "🔴"
                
                # 检查风控状态
                status = "✅ 正常"
                pos_risk = self.check_position_risk(code, price, cost, pos.get('shares', 0))
                for action in pos_risk.get('actions', []):
                    if action.get('priority') == 'HIGH':
                        status = f"⚠️ {action['action']}"
                    elif action.get('type') == 'TRAILING_STOP':
                        status = f"🎯 {action['action']}"
                
                output += f"\n{emoji} {name}: ¥{price:.2f} ({profit_pct:+.1f}%) {status}"
        
        # 紧急动作
        if report['urgent_actions']:
            output += f"""
{'='*50}
⚠️ **紧急动作**
"""
            for action in report['urgent_actions']:
                output += f"\n🔴 {action['code']}: {action['action']} - {action['reason']}"
        
        output += f"""
{'='*50}
⚙️ **风控参数**
   固定止损: {self.position_config['stop_loss']*100:.0f}%
   跟踪止盈: {self.position_config['trailing_stop']*100:.0f}% (盈利>{self.position_config['trailing_start']*100:.0f}%后启用)
   最大回撤: {self.account_config['max_drawdown']*100:.0f}%
   最大仓位: {self.account_config['max_position_ratio']*100:.0f}%
{'='*50}
"""
        
        return output


# 测试
if __name__ == "__main__":
    print("🧪 测试增强版风控系统...")
    
    rm = EnhancedRiskManager()
    rm.set_capital(100000)
    
    # 模拟持仓
    positions = {
        "603960": {"name": "克莱机电", "price": 25.78, "cost": 17.41, "shares": 1500, "holding_days": 10},
        "600938": {"name": "中国海油", "price": 43.41, "cost": 18.51, "shares": 300, "holding_days": 15},
        "600329": {"name": "达仁堂", "price": 41.22, "cost": 41.37, "shares": 500, "holding_days": 5},
        "002737": {"name": "葵花药业", "price": 13.55, "cost": 14.82, "shares": 2500, "holding_days": 20},
    }
    
    total_value = sum(p['price'] * p['shares'] for p in positions.values())
    rm.set_positions(positions)
    
    # 生成报告
    report = rm.generate_report(positions, total_value)
    print(report)
    
    # 综合检查
    result = rm.comprehensive_check(positions, total_value, index_change=-0.02)
    print(f"\n✅ 风控通过: {result['approved']}")
    print(f"⚠️ 紧急动作: {len(result['urgent_actions'])} 项")
    
    print("\n✅ 测试完成")
