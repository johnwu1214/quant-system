#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小龙虾自主量化交易机器人 v2
完全自主选股、交易、持仓管理
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import get_stock_daily, get_stock_realtime, get_daily_tushare
from strategies.advanced_strategies_v2 import CompositeSignal, RiskManagement
from strategies.factor_selection import FactorSelection
import json
from datetime import datetime
import random


class AutoTrader:
    """自主量化交易员"""
    
    def __init__(self):
        self.capital = 100000  # 10万模拟金
        self.cash = 100000
        self.positions = {}  # {code: {'name': xx, 'shares': xx, 'avg_cost': xx}}
        
        # 交易参数
        self.max_positions = 5  # 最多5只
        self.max_position_pct = 0.25  # 单只最高25%
        self.buy_threshold = 70  # 买入置信度
        self.sell_threshold = 50  # 卖出置信度
        self.stop_loss_pct = -8  # 止损8%
        self.take_profit_pct = 15  # 止盈15%
        
        # 选股池 - 扩大范围
        self.stock_pool = self._build_stock_pool()
        
        # 历史
        self.trade_history = []
        
    def _build_stock_pool(self) -> list:
        """构建选股池"""
        # A股热门标的
        return [
            # 持仓继续关注
            {'code': '603960', 'name': '克莱机电'},
            {'code': '600938', 'name': '中国海油'},
            {'code': '600329', 'name': '达仁堂'},
            {'code': '002737', 'name': '葵花药业'},
            {'code': '603639', 'name': '应流股份'},
            {'code': '300662', 'name': '杰恩设计'},
            {'code': '601006', 'name': '大秦铁路'},
            # 扩展候选
            {'code': '600519', 'name': '贵州茅台'},
            {'code': '000858', 'name': '五粮液'},
            {'code': '601318', 'name': '中国平安'},
            {'code': '600036', 'name': '招商银行'},
            {'code': '300750', 'name': '宁德时代'},
            {'code': '002594', 'name': '比亚迪'},
            {'code': '600900', 'name': '长江电力'},
            {'code': '601888', 'name': '中国中免'},
        ]
    
    def get_realtime_price(self, code: str) -> float:
        """获取实时价格"""
        try:
            rt = get_stock_realtime(code)
            return rt.get('price', 0)
        except:
            return 0
    
    def analyze(self, code: str, name: str) -> dict:
        """综合分析"""
        result = {
            'code': code,
            'name': name,
            'price': 0,
            'score': 0,
            'decision': '观望',
            'reasons': []
        }
        
        # 获取数据
        df = get_daily_tushare(code, 60)
        if df.empty or len(df) < 30:
            return result
        
        price = df['close'].iloc[-1]
        result['price'] = price
        
        # 技术分析
        cs = CompositeSignal()
        tech = cs.analyze(df)
        
        # 因子评分
        fs = FactorSelection()
        factor = fs.comprehensive_score(df)
        
        # 综合打分 (技术40% + 因子60%)
        tech_score = tech['buy_score'] * 15 + tech['confidence'] * 0.3
        factor_score = factor['total_score'] * 0.6
        
        result['score'] = min(tech_score + factor_score, 100)
        
        # 决策 - 综合考虑技术和因子
        if tech['buy_score'] >= 2 and factor['total_score'] >= 40:
            result['decision'] = '强烈买入'
            result['reasons'].append(f"技术{tech['buy_score']}个看涨+因子{factor['total_score']}")
        elif tech['buy_score'] > tech['sell_score']:
            result['decision'] = '买入'
            result['reasons'].append('技术面偏多')
        elif factor['total_score'] >= 60:
            # 因子评分高，可能被低估
            result['decision'] = '关注'
            result['reasons'].append(f'因子评分高({factor["total_score"]})')
        elif tech['sell_score'] >= 2:
            result['decision'] = '卖出'
            result['reasons'].append(f"技术{tech['sell_score']}个看跌")
        else:
            result['decision'] = '观望'
            result['reasons'].append('方向不明')
        
        # 附加信息
        result['tech'] = tech
        result['factor'] = factor
        result['confidence'] = tech.get('confidence', 0)
        
        return result
    
    def should_buy(self, analysis: dict) -> bool:
        """判断是否买入"""
        # 检查是否已有持仓
        if analysis['code'] in self.positions:
            return False
        
        # 检查是否满仓
        if len(self.positions) >= self.max_positions:
            return False
        
        # 检查资金
        if self.cash < analysis['price'] * 100:
            return False
        
        # 买入条件 - 更灵活
        if '买入' in analysis['decision'] or '关注' in analysis['decision']:
            # 强烈买入或因子好的关注都可以买
            if analysis['score'] >= 50:  # 降低到50
                return True
        
        return False
    
    def should_sell(self, code: str, analysis: dict) -> bool:
        """判断是否卖出"""
        if code not in self.positions:
            return False
        
        pos = self.positions[code]
        price = analysis.get('price', 0)
        
        if price <= 0:
            return False
        
        # 盈亏计算
        pl_pct = (price - pos['avg_cost']) / pos['avg_cost'] * 100
        
        # 止损
        if pl_pct <= self.stop_loss_pct:
            return True
        
        # 止盈
        if pl_pct >= self.take_profit_pct:
            return True
        
        # 技术面转空
        if analysis.get('tech', {}).get('sell_score', 0) >= 2:
            return True
        
        return False
    
    def execute_buy(self, analysis: dict) -> bool:
        """执行买入"""
        code = analysis['code']
        name = analysis['name']
        price = analysis['price']
        
        # 计算买入金额 (25%仓位)
        target_amount = self.capital * self.max_position_pct
        shares = int(target_amount / price / 100) * 100  # 整手
        
        if shares <= 0:
            return False
        
        cost = shares * price
        
        if cost > self.cash:
            # 钱不够，买能买的
            shares = int(self.cash / price / 100) * 100
            cost = shares * price
        
        if shares <= 0:
            return False
        
        # 执行
        self.cash -= cost
        self.positions[code] = {
            'name': name,
            'shares': shares,
            'avg_cost': price,
            'buy_date': datetime.now().strftime('%Y-%m-%d')
        }
        
        # 记录
        self.trade_history.append({
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'code': code,
            'name': name,
            'action': 'BUY',
            'price': price,
            'shares': shares,
            'amount': cost
        })
        
        return True
    
    def execute_sell(self, code: str, price: float) -> bool:
        """执行卖出"""
        if code not in self.positions:
            return False
        
        pos = self.positions[code]
        shares = pos['shares']
        
        revenue = shares * price
        cost = shares * pos['avg_cost']
        profit = revenue - cost
        pl_pct = profit / cost * 100
        
        # 执行
        self.cash += revenue
        del self.positions[code]
        
        # 记录
        self.trade_history.append({
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'code': code,
            'name': pos['name'],
            'action': 'SELL',
            'price': price,
            'shares': shares,
            'amount': revenue,
            'profit': profit,
            'pl_pct': pl_pct
        })
        
        return True
    
    def run(self) -> dict:
        """运行交易"""
        print(f"\n{'='*60}")
        print(f"🦞 自主量化交易 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print('='*60)
        
        print(f"\n💰 初始资金: ¥{self.capital:,}")
        print(f"💵 可用现金: ¥{self.cash:,}")
        print(f"📦 持仓数量: {len(self.positions)}只")
        
        # 1. 先检查持仓是否需要卖出
        print(f"\n🔍 检查持仓...")
        sell_list = []
        for code, pos in list(self.positions.items()):
            analysis = self.analyze(code, pos['name'])
            analysis['price'] = self.get_realtime_price(code)
            
            if self.should_sell(code, analysis):
                sell_list.append((code, analysis['price'], analysis))
                print(f"  🚫 {pos['name']}: 触发卖出条件")
            else:
                pl = (analysis.get('price', 0) - pos['avg_cost']) / pos['avg_cost'] * 100
                print(f"  ✅ {pos['name']}: 持有 (盈亏{pl:+.1f}%)")
        
        # 执行卖出
        for code, price, _ in sell_list:
            self.execute_sell(code, price)
            print(f"  ✓ 已卖出 {code}")
        
        # 2. 选股
        print(f"\n🔍 选股池扫描 ({len(self.stock_pool)}只)...")
        candidates = []
        
        for stock in self.stock_pool:
            # 跳过已有持仓
            if stock['code'] in self.positions:
                continue
            
            analysis = self.analyze(stock['code'], stock['name'])
            analysis['price'] = self.get_realtime_price(stock['code'])
            
            if analysis['price'] <= 0:
                continue
            
            if self.should_buy(analysis):
                candidates.append(analysis)
                print(f"  🟢 {stock['name']}: 综合得分{analysis['score']:.0f} - {analysis['decision']}")
        
        # 按得分排序
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # 3. 执行买入
        print(f"\n📈 执行买入...")
        buy_count = self.max_positions - len(self.positions)
        
        for i, candidate in enumerate(candidates[:buy_count]):
            if self.execute_buy(candidate):
                print(f"  ✅ 买入 {candidate['name']} @ ¥{candidate['price']:.2f}")
        
        # 4. 统计
        total_value = self.cash
        positions_info = []
        
        print(f"\n📊 持仓明细:")
        for code, pos in self.positions.items():
            price = self.get_realtime_price(code)
            value = price * pos['shares']
            pl = (price - pos['avg_cost']) / pos['avg_cost'] * 100
            total_value += value
            
            print(f"  {pos['name']}: {pos['shares']}股 @ ¥{price:.2f} (盈亏{pl:+.1f}%)")
            positions_info.append({
                'code': code,
                'name': pos['name'],
                'shares': pos['shares'],
                'price': price,
                'avg_cost': pos['avg_cost'],
                'pl_pct': pl
            })
        
        # 计算收益率
        return_pct = (total_value - self.capital) / self.capital * 100
        
        print(f"\n{'='*60}")
        print(f"📈 总资产: ¥{total_value:,}")
        print(f"📈 收益率: {return_pct:+.2f}%")
        print(f"{'='*60}")
        
        result = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M'),
            'capital': self.capital,
            'cash': self.cash,
            'total_value': total_value,
            'return_pct': return_pct,
            'positions': positions_info,
            'trade_history': self.trade_history[-10:]
        }
        
        # 保存
        self._save(result)
        
        return result
    
    def _save(self, result: dict):
        """保存结果"""
        os.makedirs('data', exist_ok=True)
        
        # 保存当前状态
        state = {
            'cash': self.cash,
            'positions': self.positions,
            'trade_history': self.trade_history,
            'capital': self.capital
        }
        with open('data/auto_trader_state.json', 'w') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        
        # 保存交易记录
        with open('data/auto_trader_log.json', 'a') as f:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
    
    def load(self):
        """加载状态"""
        try:
            with open('data/auto_trader_state.json', 'r') as f:
                state = json.load(f)
            self.cash = state['cash']
            self.positions = state['positions']
            self.trade_history = state['trade_history']
        except:
            pass


def main():
    trader = AutoTrader()
    trader.load()
    result = trader.run()
    return result


if __name__ == "__main__":
    main()
