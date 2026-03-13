#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小龙虾自主交易机器人
完全自主运行，自负盈亏
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import get_stock_daily, get_stock_realtime, get_daily_tushare
from strategies.advanced_strategies_v2 import CompositeSignal, RiskManagement
from simulated_trading import SimulatedPortfolio
from risk_alert import RiskAlert
import json
from datetime import datetime


class TradingBot:
    """自主交易机器人"""
    
    def __init__(self):
        # 模拟资金10万
        self.portfolio = SimulatedPortfolio(100000, "小龙虾自主交易")
        
        # 选股池
        self.stock_pool = [
            {'code': '603960', 'name': '克莱机电'},
            {'code': '600938', 'name': '中国海油'},
            {'code': '600329', 'name': '达仁堂'},
            {'code': '002737', 'name': '葵花药业'},
            {'code': '603639', 'name': '应流股份'},
            {'code': '300662', 'name': '杰恩设计'},
            {'code': '601006', 'name': '大秦铁路'},
        ]
        
        # 风控
        self.risk = RiskAlert()
        
        # 交易统计
        self.stats_file = 'data/trading_stats.json'
        
    def analyze_stock(self, code: str, name: str) -> dict:
        """分析股票"""
        result = {'code': code, 'name': name, 'decision': '持有', 'confidence': 0}
        
        # 获取数据
        df = get_daily_tushare(code, 60)
        if df.empty:
            return result
        
        # 技术分析
        cs = CompositeSignal()
        analysis = cs.analyze(df)
        
        result['decision'] = analysis.get('decision', '持有')
        result['confidence'] = analysis.get('confidence', 0)
        result['buy_score'] = analysis.get('buy_score', 0)
        result['sell_score'] = analysis.get('sell_score', 0)
        
        # 当前价格
        rt = get_stock_realtime(code)
        result['price'] = rt.get('price', 0)
        
        return result
    
    def should_buy(self, signal: dict) -> bool:
        """判断是否买入"""
        # 置信度70%以上 且 买入信号
        if '买入' in signal['decision'] and signal['confidence'] >= 70:
            # 且不在持仓中
            if signal['code'] not in self.portfolio.positions:
                return True
        return False
    
    def should_sell(self, signal: dict) -> bool:
        """判断是否卖出"""
        # 持仓中 且 卖出信号
        if signal['code'] in self.portfolio.positions:
            # 置信度50%以上 或 止损
            if '卖出' in signal['decision'] and signal['confidence'] >= 50:
                return True
        return False
    
    def run_trading(self) -> dict:
        """运行交易"""
        print(f"\n{'='*60}")
        print(f"🦞 小龙虾自主交易 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print('='*60)
        
        actions = []
        
        # 分析所有股票
        signals = {}
        for stock in self.stock_pool:
            print(f"\n分析 {stock['name']}...")
            signal = self.analyze_stock(stock['code'], stock['name'])
            signals[stock['code']] = signal
            
            decision = signal['decision']
            confidence = signal['confidence']
            price = signal.get('price', 0)
            
            print(f"  价格: ¥{price}")
            print(f"  决策: {decision} (置信度 {confidence}%)")
            
            # 买入判断
            if self.should_buy(signal):
                if price > 0:
                    success = self.portfolio.buy(
                        stock['code'], 
                        stock['name'], 
                        price, 
                        100  # 买100股
                    )
                    if success:
                        actions.append(f"买入 {stock['name']} @ ¥{price}")
                        print(f"  ✅ 买入成功!")
            
            # 卖出判断
            elif self.should_sell(signal):
                if price > 0:
                    success = self.portfolio.sell(stock['code'], price)
                    if success:
                        actions.append(f"卖出 {stock['name']} @ ¥{price}")
                        print(f"  ✅ 卖出成功!")
            
            # 持有
            else:
                print(f"  ➡️ 持有")
        
        # 更新权益
        prices = {s['code']: s.get('price', 0) for s in signals.values()}
        portfolio_value = self.portfolio.get_portfolio_value(prices)
        
        # 统计
        stats = self.portfolio.get_stats()
        
        print(f"\n{'='*60}")
        print("📊 交易结果")
        print('='*60)
        print(f"  资金: ¥{stats['current_value']:,.0f}")
        print(f"  收益率: {stats['return_pct']:+.2f}%")
        print(f"  持仓: {stats['position_count']}只")
        print(f"  交易次数: {stats['total_trades']}")
        
        if actions:
            print(f"\n📝 今日操作:")
            for a in actions:
                print(f"  - {a}")
        else:
            print(f"\n📝 今日操作: 无"
)
        
        return {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'actions': actions,
            'stats': stats,
            'positions': self.portfolio.get_positions()
        }
    
    def save_result(self, result: dict):
        """保存结果"""
        # 确保目录存在
        os.makedirs('data', exist_ok=True)
        
        # 保存交易记录
        with open('data/trading_log.json', 'a', encoding='utf-8') as f:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
        
        # 保存组合状态
        self.portfolio.save('data/portfolio.json')
    
    def load_portfolio(self):
        """加载组合"""
        if os.path.exists('data/portfolio.json'):
            self.portfolio.load('data/portfolio.json')


def main():
    """主函数"""
    bot = TradingBot()
    
    # 尝试加载之前的组合
    bot.load_portfolio()
    
    # 运行交易
    result = bot.run_trading()
    
    # 保存结果
    bot.save_result(result)
    
    return result


if __name__ == "__main__":
    main()
