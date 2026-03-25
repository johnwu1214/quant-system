#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风控预警系统
"""
from typing import Dict, List
from datetime import datetime


class RiskAlert:
    """风险预警"""
    
    def __init__(self):
        # 预警阈值配置
        self.config = {
            'stop_loss_pct': -5.0,      # 止损线 -5%
            'stop_profit_pct': 20.0,     # 止盈线 +20%
            'max_position_pct': 30.0,    # 单只股票最高仓位30%
            'max_drawdown_pct': 15.0,   # 最大回撤 15%
            'volatility_threshold': 5.0,  # 日波动超过5%预警
        }
    
    def check_position(self, code: str, name: str, cost: float, price: float, 
                       total_capital: float) -> List[Dict]:
        """检查持仓风险"""
        alerts = []
        
        # 计算盈亏
        pl_pct = (price - cost) / cost * 100 if cost > 0 else 0
        pl_value = (price - cost)
        
        # 止损检查
        if pl_pct <= self.config['stop_loss_pct']:
            alerts.append({
                'type': '🚨 止损',
                'code': code,
                'name': name,
                'message': f'亏损达到{abs(pl_pct):.1f}%，建议止损',
                'action': 'SELL',
                'priority': 'HIGH'
            })
        # 止盈检查
        elif pl_pct >= self.config['stop_profit_pct']:
            alerts.append({
                'type': '📈 止盈',
                'code': code,
                'name': name,
                'message': f'盈利已达{pl_pct:.1f}%，可考虑分批止盈',
                'action': 'PARTIAL_SELL',
                'priority': 'MEDIUM'
            })
        # 接近止损
        elif pl_pct <= self.config['stop_loss_pct'] + 2:
            alerts.append({
                'type': '⚠️ 预警',
                'code': code,
                'name': name,
                'message': f'接近止损线，当前亏损{pl_pct:.1f}%',
                'action': 'WATCH',
                'priority': 'MEDIUM'
            })
        
        return alerts
    
    def check_portfolio(self, positions: List[Dict], total_capital: float) -> List[Dict]:
        """检查组合风险"""
        alerts = []
        
        # 检查仓位集中度
        for pos in positions:
            position_pct = pos.get('market_value', 0) / total_capital * 100
            if position_pct > self.config['max_position_pct']:
                alerts.append({
                    'type': '⚠️ 仓位集中',
                    'code': pos['code'],
                    'name': pos['name'],
                    'message': f'仓位占比{position_pct:.1f}%，超过{self.config["max_position_pct"]}%上限',
                    'action': 'REDUCE',
                    'priority': 'MEDIUM'
                })
        
        # 检查总持仓比例
        total_position = sum(p.get('market_value', 0) for p in positions)
        position_ratio = total_position / total_capital * 100 if total_capital > 0 else 0
        
        if position_ratio > 90:
            alerts.append({
                'type': '⚠️ 满仓',
                'code': 'ALL',
                'name': '组合',
                'message': f'总仓位{position_ratio:.1f}%，建议预留资金',
                'action': 'CASH',
                'priority': 'LOW'
            })
        elif position_ratio < 20:
            alerts.append({
                'type': '⚠️ 空仓',
                'code': 'ALL',
                'name': '组合',
                'message': f'总仓位{position_ratio:.1f}%，资金利用率低',
                'action': 'BUY',
                'priority': 'LOW'
            })
        
        return alerts
    
    def generate_report(self, positions: List[Dict], total_capital: float) -> str:
        """生成风控报告"""
        all_alerts = []
        
        # 检查每只股票
        for pos in positions:
            cost = pos.get('cost', 0)
            price = pos.get('price', 0)
            if cost > 0 and price > 0:
                alerts = self.check_position(
                    pos['code'], pos['name'], cost, price, total_capital
                )
                all_alerts.extend(alerts)
        
        # 检查组合
        portfolio_alerts = self.check_portfolio(positions, total_capital)
        all_alerts.extend(portfolio_alerts)
        
        # 生成报告
        if not all_alerts:
            return "✅ 风控检查通过，无预警"
        
        report = "🚨 **风控预警报告**\n\n"
        
        # 按优先级排序
        high = [a for a in all_alerts if a['priority'] == 'HIGH']
        medium = [a for a in all_alerts if a['priority'] == 'MEDIUM']
        low = [a for a in all_alerts if a['priority'] == 'LOW']
        
        if high:
            report += "**高优先级:**\n"
            for a in high:
                report += f"  {a['type']} {a['name']}: {a['message']}\n"
        
        if medium:
            report += "\n**中优先级:**\n"
            for a in medium:
                report += f"  {a['type']} {a['name']}: {a['message']}\n"
        
        if low:
            report += "\n**低优先级:**\n"
            for a in low:
                report += f"  {a['type']} {a['name']}: {a['message']}\n"
        
        return report


if __name__ == "__main__":
    # 测试
    risk = RiskAlert()
    
    positions = [
        {'code': '603960', 'name': '克莱机电', 'cost': 17.41, 'price': 26.0, 'market_value': 39000},
        {'code': '002737', 'name': '葵花药业', 'cost': 14.82, 'price': 14.0, 'market_value': 35000},
    ]
    
    total_capital = 100000
    
    report = risk.generate_report(positions, total_capital)
    print(report)
