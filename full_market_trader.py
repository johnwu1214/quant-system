#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小龙虾全市场选股机器人
从全市场筛选最优股票
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import get_stock_daily, get_stock_realtime, get_daily_tushare
from strategies.advanced_strategies_v2 import CompositeSignal
from strategies.factor_selection import FactorSelection
import json
from datetime import datetime


class FullMarketTrader:
    """全市场选股机器人"""
    
    def __init__(self):
        self.capital = 100000
        self.cash = 100000
        self.positions = {}
        self.trade_history = []
        
        # 交易参数
        self.max_positions = 5
        self.max_position_pct = 0.20  # 20%仓位
        
        # 热门股票池（从全市场筛选）
        self.stock_pool = self._build_pool()
        
        print(f"选股池大小: {len(self.stock_pool)}只")
    
    def _build_pool(self) -> list:
        """构建热门股票池"""
        # 从各行业龙头中筛选
        pool = [
            # 银行
            {'code': '601398', 'name': '工商银行'},
            {'code': '601939', 'name': '建设银行'},
            {'code': '601288', 'name': '农业银行'},
            {'code': '600036', 'name': '招商银行'},
            # 保险
            {'code': '601318', 'name': '中国平安'},
            {'code': '601601', 'name': '中国人保'},
            # 白酒
            {'code': '600519', 'name': '贵州茅台'},
            {'code': '000858', 'name': '五粮液'},
            {'code': '600809', 'name': '山西汾酒'},
            {'code': '000596', 'name': '古井贡酒'},
            # 消费
            {'code': '600887', 'name': '伊利股份'},
            {'code': '603288', 'name': '海天味业'},
            {'code': '002027', 'name': '分众传媒'},
            # 医药
            {'code': '600276', 'name': '恒瑞医药'},
            {'code': '300760', 'name': '迈瑞医疗'},
            {'code': '002252', 'name': '上海莱士'},
            {'code': '000538', 'name': '云南白药'},
            # 新能源
            {'code': '300750', 'name': '宁德时代'},
            {'code': '002594', 'name': '比亚迪'},
            {'code': '600438', 'name': '通威股份'},
            {'code': '601012', 'name': '隆基绿能'},
            # 科技
            {'code': '600030', 'name': '中信证券'},
            {'code': '688981', 'name': '中芯国际'},
            {'code': '002475', 'name': '立讯精密'},
            {'code': '000333', 'name': '美的集团'},
            # 基建
            {'code': '601668', 'name': '中国建筑'},
            {'code': '601390', 'name': '中国中铁'},
            {'code': '601186', 'name': '中国铁建'},
            # 电力
            {'code': '600900', 'name': '长江电力'},
            {'code': '600025', 'name': '华能水电'},
            # 航运
            {'code': '601919', 'name': '中远海控'},
            {'code': '601872', 'name': '招商轮船'},
            # 地产
            {'code': '000002', 'name': '万科A'},
            {'code': '600048', 'name': '保利发展'},
            # 传媒
            {'code': '300033', 'name': '同花顺'},
            {'code': '002230', 'name': '科大讯飞'},
            # 物流
            {'code': '002352', 'name': '顺丰控股'},
            {'code': '600233', 'name': '圆通速递'},
            # 电商
            {'code': '603799', 'name': '华友钴业'},
            # 其他龙头
            {'code': '601888', 'name': '中国中免'},
            {'code': '600104', 'name': '上汽集团'},
            {'code': '601668', 'name': '中国建筑'},
        ]
        return pool
    
    def analyze(self, code: str, name: str) -> dict:
        """分析股票"""
        result = {
            'code': code, 'name': name, 'price': 0,
            'score': 0, 'decision': '观望'
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
        
        # 因子分析  
        fs = FactorSelection()
        factor = fs.comprehensive_score(df)
        
        # 综合得分
        score = tech['buy_score'] * 20 + tech['confidence'] * 0.3 + factor['total_score'] * 0.4
        result['score'] = min(score, 100)
        
        # 决策
        if tech['buy_score'] >= 2 and factor['total_score'] >= 40:
            result['decision'] = '强烈买入'
        elif tech['buy_score'] > tech['sell_score']:
            result['decision'] = '买入'
        elif factor['total_score'] >= 60:
            result['decision'] = '关注'
        elif tech['sell_score'] >= 2:
            result['decision'] = '卖出'
        else:
            result['decision'] = '观望'
        
        result['tech'] = tech
        result['factor'] = factor
        
        return result
    
    def get_price(self, code: str) -> float:
        """获取实时价格"""
        try:
            rt = get_stock_realtime(code)
            return rt.get('price', 0)
        except:
            return 0
    
    def run(self) -> dict:
        """运行"""
        print(f"\n{'='*60}")
        print(f"🦞 全市场选股 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print('='*60)
        
        print(f"\n💰 资金: ¥{self.cash:,}")
        
        # 1. 检查持仓
        print(f"\n🔍 检查持仓...")
        for code in list(self.positions.keys()):
            pos = self.positions[code]
            price = self.get_price(code)
            if price > 0:
                pl = (price - pos['avg_cost']) / pos['avg_cost'] * 100
                print(f"  {pos['name']}: 盈亏{pl:+.1f}%")
        
        # 2. 全市场选股
        print(f"\n🔍 全市场选股扫描 ({len(self.stock_pool)}只)...")
        
        candidates = []
        for stock in self.stock_pool:
            if stock['code'] in self.positions:
                continue
            
            analysis = self.analyze(stock['code'], stock['name'])
            analysis['price'] = self.get_price(stock['code'])
            
            if analysis['price'] <= 0:
                continue
            
            if analysis['score'] >= 40 and '买' in analysis['decision']:
                candidates.append(analysis)
                print(f"  🟢 {stock['name']}: {analysis['decision']} (得分{analysis['score']:.0f})")
        
        # 排序
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # 3. 买入
        print(f"\n📈 执行买入...")
        slots = self.max_positions - len(self.positions)
        
        for cand in candidates[:slots]:
            if self.cash < cand['price'] * 100:
                continue
            
            # 买入
            shares = int(self.cash * self.max_position_pct / cand['price'] / 100) * 100
            if shares <= 0:
                continue
            
            cost = shares * cand['price']
            self.cash -= cost
            self.positions[cand['code']] = {
                'name': cand['name'],
                'shares': shares,
                'avg_cost': cand['price']
            }
            
            print(f"  ✅ 买入 {cand['name']} {shares}股 @ ¥{cand['price']:.2f}")
            
            self.trade_history.append({
                'date': datetime.now().strftime('%Y-%m-%d'),
                'code': cand['code'],
                'name': cand['name'],
                'action': 'BUY',
                'price': cand['price'],
                'shares': shares
            })
        
        # 4. 统计
        total = self.cash
        print(f"\n📊 持仓:")
        for code, pos in self.positions.items():
            price = self.get_price(code)
            value = price * pos['shares']
            pl = (price - pos['avg_cost']) / pos['avg_cost'] * 100
            total += value
            print(f"  {pos['name']}: {pos['shares']}股 @ ¥{price:.2f} ({pl:+.1f}%)")
        
        return_pct = (total - self.capital) / self.capital * 100
        
        print(f"\n📈 总资产: ¥{total:,} ({return_pct:+.2f}%)")
        
        # 保存
        self._save()
        
        return {
            'total': total,
            'return_pct': return_pct,
            'positions': len(self.positions)
        }
    
    def _save(self):
        """保存"""
        os.makedirs('data', exist_ok=True)
        state = {
            'cash': self.cash,
            'positions': self.positions,
            'capital': self.capital
        }
        with open('data/full_market_trader.json', 'w') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def load(self):
        """加载"""
        try:
            with open('data/full_market_trader.json', 'r') as f:
                state = json.load(f)
            self.cash = state['cash']
            self.positions = state['positions']
        except:
            pass


if __name__ == "__main__":
    trader = FullMarketTrader()
    trader.load()
    trader.run()
