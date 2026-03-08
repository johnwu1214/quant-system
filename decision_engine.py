#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小龙虾量化工作室 - 自主决策系统
目标：每天自动分析，自主给出买卖决策
"""
import os
import sys
from datetime import datetime
from data_fetcher import get_stock_daily, get_stock_realtime, get_macd_moma
from strategies.advanced_strategies import (
    MAStrategy, RSIStrategy, MACDStrategy, 
    BOLLStrategy, VolumeStrategy, CompositeStrategy
)

# 持仓配置
POSITIONS = [
    {'code': '300001', 'name': '克莱机电', 'shares': 1500, 'cost': 17.41},
    {'code': '600938', 'name': '中国海油', 'shares': 300, 'cost': 18.51},
    {'code': '600329', 'name': '达仁堂', 'shares': 500, 'cost': 41.37},
    {'code': '002737', 'name': '葵花药业', 'shares': 2500, 'cost': 14.82},
]

CASH = 80934.48  # 可用资金


class QuantDecisionMaker:
    """量化决策引擎"""
    
    def __init__(self):
        self.strategies = {
            'MA': MAStrategy(5, 20),
            'RSI': RSIStrategy(14),
            'MACD': MACDStrategy(),
            'BOLL': BOLLStrategy(),
            'VOL': VolumeStrategy()
        }
    
    def analyze(self, stock_code: str) -> dict:
        """全面分析一只股票"""
        result = {
            'code': stock_code,
            'price': 0,
            'signals': {},
            'scores': {'buy': 0, 'sell': 0},
            'decision': '持有',
            'confidence': 0,
            'reason': ''
        }
        
        # 获取数据
        df = get_stock_daily(stock_code, 30)
        if df.empty:
            result['error'] = '数据获取失败'
            return result
        
        rt = get_stock_realtime(stock_code)
        result['price'] = rt.get('price', 0)
        
        # 各指标打分
        for name, strategy in self.strategies.items():
            signal = strategy.get_current_signal(df)
            result['signals'][name] = signal
            
            # 打分
            if '买入' in signal or '金叉' in signal or '超卖' in signal:
                result['scores']['buy'] += 1
            elif '卖出' in signal or '死叉' in signal or '超买' in signal:
                result['scores']['sell'] += 1
        
        # 决策
        buy_score = result['scores']['buy']
        sell_score = result['scores']['sell']
        
        if buy_score >= 3:
            result['decision'] = '强烈买入'
            result['confidence'] = min(buy_score * 20, 95)
            result['reason'] = f'{buy_score}个指标看涨'
        elif buy_score > sell_score:
            result['decision'] = '买入'
            result['confidence'] = 50 + (buy_score - sell_score) * 15
            result['reason'] = '多数指标偏多'
        elif sell_score >= 3:
            result['decision'] = '强烈卖出'
            result['confidence'] = min(sell_score * 20, 95)
            result['reason'] = f'{sell_score}个指标看跌'
        elif sell_score > buy_score:
            result['decision'] = '卖出'
            result['confidence'] = 50 + (sell_score - buy_score) * 15
            result['reason'] = '多数指标偏空'
        else:
            result['decision'] = '持有'
            result['confidence'] = 30
            result['reason'] = '方向不明'
        
        return result
    
    def daily_report(self) -> dict:
        """生成每日报告"""
        report = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'positions': [],
            'total_value': 0,
            'total_cost': 0,
            'total_pl': 0,
            'decisions': []
        }
        
        # 分析持仓
        for pos in POSITIONS:
            analysis = self.analyze(pos['code'])
            price = analysis.get('price', 0)
            market_value = price * pos['shares']
            cost = pos['cost'] * pos['shares']
            pl = market_value - cost
            pl_pct = pl / cost * 100 if cost > 0 else 0
            
            position_data = {
                'name': pos['name'],
                'code': pos['code'],
                'price': price,
                'market_value': market_value,
                'cost': cost,
                'pl': pl,
                'pl_pct': pl_pct,
                'decision': analysis['decision'],
                'confidence': analysis.get('confidence', 0),
                'reason': analysis.get('reason', ''),
                'signals': analysis.get('signals', {})
            }
            
            report['positions'].append(position_data)
            report['total_value'] += market_value
            report['total_cost'] += cost
            report['total_pl'] += pl
            
            # 决策汇总
            if analysis['decision'] in ['强烈买入', '买入']:
                report['decisions'].append({
                    'name': pos['name'],
                    'action': analysis['decision'],
                    'confidence': analysis.get('confidence', 0)
                })
        
        report['total_assets'] = report['total_value'] + CASH
        report['total_pl_pct'] = report['total_pl'] / report['total_cost'] * 100 if report['total_cost'] > 0 else 0
        
        return report
    
    def generate_message(self) -> str:
        """生成飞书消息"""
        report = self.daily_report()
        
        msg = f"""
🦞 **小龙虾量化日报** - {report['date']}
{'='*50}

📊 **持仓状态**
"""
        
        for p in report['positions']:
            emoji = '🟢' if p['pl'] > 0 else '🔴'
            action_emoji = '⬆️' if '买' in p['decision'] else '⬇️' if '卖' in p['decision'] else '➡️'
            
            msg += f"""
{emoji} {p['name']} ({p['code']})
   当前价: ¥{p['price']:.2f} | 盈亏: {p['pl']:+,.0f} ({p['pl_pct']:+.1f}%)
   📌 决策: {p['decision']} {action_emoji} (置信度: {p['confidence']:.0f}%)
   📝 原因: {p['reason']}
"""
        
        # 汇总
        total_emoji = '🟢' if report['total_pl'] > 0 else '🔴'
        
        msg += f"""
{'='*50}
💰 **资产汇总**
   总市值: ¥{report['total_value']:,.0f}
   可用现金: ¥{CASH:,.0f}
   总资产: ¥{report['total_assets']:,.0f}
   总盈亏: {total_emoji} {report['total_pl']:+,.0f} ({report['total_pl_pct']:+.1f}%)
"""
        
        # 今日决策
        if report['decisions']:
            msg += f"""
{'='*50}
🎯 **今日操作建议**
"""
            for d in report['decisions']:
                msg += f"   • {d['name']}: {d['action']} (置信度 {d['confidence']:.0f}%)\n"
        
        msg += f"""
{'='*50}
🦞 系统自动生成 | 仅供参考
"""
        
        return msg


# 测试
if __name__ == "__main__":
    dm = QuantDecisionMaker()
    print(dm.generate_message())
