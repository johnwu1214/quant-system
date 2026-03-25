#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
因子选股系统
基于多因子模型筛选强势股票
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from collections import defaultdict


class FactorSelection:
    """
    多因子选股模型
    
    因子类型：
    1. 价值因子 - 市盈率、市净率、股息率
    2. 成长因子 - 净利润增速、营收增速
    3. 动量因子 - 近期涨跌幅
    4. 质量因子 - ROE、毛利率
    5. 规模因子 - 总市值、流通市值
    """
    
    def __init__(self):
        self.factors = {}
    
    def momentum_factor(self, df: pd.DataFrame, periods: List[int] = [5, 10, 20]) -> Dict:
        """
        动量因子
        近期涨幅越大，动量因子越好
        """
        results = {}
        for period in periods:
            if len(df) >= period:
                change = (df['close'].iloc[-1] / df['close'].iloc[-period] - 1) * 100
                results[f'{period}日'] = change
        return results
    
    def volatility_factor(self, df: pd.DataFrame, period: int = 20) -> Dict:
        """
        波动率因子
        波动越小，风险越低
        """
        if len(df) < period:
            return {'volatility': 0, 'rank': '数据不足'}
        
        returns = df['close'].pct_change().tail(period)
        volatility = returns.std() * 100
        
        # 评级
        if volatility < 2:
            rank = '低波动 稳定'
        elif volatility < 4:
            rank = '中等波动'
        else:
            rank = '高波动 风险'
        
        return {'volatility': volatility, 'rank': rank}
    
    def volume_factor(self, df: pd.DataFrame, period: int = 20) -> Dict:
        """
        成交量因子
        放量说明有资金关注
        """
        if len(df) < period:
            return {'volume_ratio': 1, 'rank': '数据不足'}
        
        avg_volume = df['volume'].tail(period).mean()
        recent_volume = df['volume'].iloc[-5:].mean()
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
        
        if volume_ratio > 1.5:
            rank = '放量 活跃 🔥'
        elif volume_ratio > 1.0:
            rank = '正常'
        else:
            rank = '缩量 观望'
        
        return {'volume_ratio': volume_ratio, 'rank': rank}
    
    def trend_factor(self, df: pd.DataFrame) -> Dict:
        """
        趋势因子
        均线多头排列 = 强势
        """
        if len(df) < 20:
            return {'trend': 'unknown', 'rank': '数据不足'}
        
        ma5 = df['close'].rolling(5).mean().iloc[-1]
        ma10 = df['close'].rolling(10).mean().iloc[-1]
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        current = df['close'].iloc[-1]
        
        # 多头排列：MA5 > MA10 > MA20 > 当前价
        if ma5 > ma10 > ma20:
            trend = '多头排列 📈'
            score = 5
        elif ma5 > ma10:
            trend = '短期上涨'
            score = 3
        elif ma5 < ma10 < ma20:
            trend = '空头排列 📉'
            score = 1
        else:
            trend = '横盘整理'
            score = 2
        
        return {
            'trend': trend,
            'ma5': ma5,
            'ma10': ma10,
            'ma20': ma20,
            'score': score
        }
    
    def relative_strength(self, df: pd.DataFrame, period: int = 20) -> Dict:
        """
        相对强弱
        跑赢大盘 = 强于市场
        """
        if len(df) < period:
            return {'rs': 0, 'rank': '数据不足'}
        
        # 假设大盘同期涨幅约10%（简化处理）
        stock_change = (df['close'].iloc[-1] / df['close'].iloc[-period] - 1) * 100
        market_change = 10  # 简化
        
        rs = stock_change - market_change
        
        if rs > 10:
            rank = '强势股 🔥'
        elif rs > 0:
            rank = '跑赢大盘'
        elif rs > -10:
            rank = '弱于大盘'
        else:
            rank = '弱势股 📉'
        
        return {'rs': rs, 'rank': rank}
    
    def comprehensive_score(self, df: pd.DataFrame) -> Dict:
        """
        综合评分
        """
        score = 0
        details = {}
        
        # 动量因子 (0-25分)
        momentum = self.momentum_factor(df)
        if '20日' in momentum:
            m = momentum['20日']
            if m > 20:
                score += 25
                details['动量'] = f'+25分 (涨{m:.1f}%)'
            elif m > 10:
                score += 15
                details['动量'] = f'+15分 (涨{m:.1f}%)'
            elif m > 0:
                score += 5
                details['动量'] = f'+5分 (涨{m:.1f}%)'
        
        # 趋势因子 (0-25分)
        trend = self.trend_factor(df)
        score += trend.get('score', 0) * 5
        details['趋势'] = f"+{trend.get('score', 0) * 5}分 ({trend.get('trend', '')})"
        
        # 成交量因子 (0-25分)
        vol = self.volume_factor(df)
        if '🔥' in vol['rank']:
            score += 25
            details['成交量'] = '+25分 (放量)'
        elif vol['volume_ratio'] > 1.0:
            score += 10
            details['成交量'] = f"+10分 (量比{vol['volume_ratio']:.1f})"
        
        # 相对强弱 (0-25分)
        rs = self.relative_strength(df)
        if '🔥' in rs['rank']:
            score += 25
            details['相对强弱'] = '+25分 (强势)'
        elif rs['rs'] > 0:
            score += 10
            details['相对强弱'] = f"+10分 (RS:{rs['rs']:.1f})"
        
        # 评级
        if score >= 80:
            rank = 'S级 强烈推荐 🌟🌟🌟'
        elif score >= 60:
            rank = 'A级 推荐 🌟🌟'
        elif score >= 40:
            rank = 'B级 关注 🌟'
        elif score >= 20:
            rank = 'C级 观望'
        else:
            rank = 'D级 不推荐'
        
        return {
            'total_score': score,
            'rank': rank,
            'details': details,
            'momentum': momentum,
            'volatility': self.volatility_factor(df),
            'volume': self.volume_factor(df),
            'trend': self.trend_factor(df),
            'rs': self.relative_strength(df)
        }
    
    def screen_stocks(self, stock_list: List[Dict], df_dict: Dict[str, pd.DataFrame]) -> List[Dict]:
        """
        股票筛选
        对列表中的股票进行综合评分排序
        """
        results = []
        
        for stock in stock_list:
            code = stock['code']
            name = stock['name']
            
            if code not in df_dict or df_dict[code].empty:
                continue
            
            df = df_dict[code]
            score_result = self.comprehensive_score(df)
            
            results.append({
                'code': code,
                'name': name,
                'score': score_result['total_score'],
                'rank': score_result['rank'],
                'details': score_result['details'],
                'momentum': score_result['momentum'],
                'trend': score_result['trend']['trend']
            })
        
        # 按分数排序
        results.sort(key=lambda x: x['score'], reverse=True)
        
        return results


class StockPool:
    """
    股票池管理
    """
    
    # 行业分类（简化版）
    INDUSTRIES = {
        '新能源': ['宁德时代', '比亚迪', '隆基绿能', '通威股份'],
        '医药': ['恒瑞医药', '药明康德', '迈瑞医疗', '爱尔眼科'],
        '消费': ['贵州茅台', '五粮液', '海天味业', '伊利股份'],
        '科技': ['腾讯控股', '阿里巴巴', '美团', '拼多多'],
        '金融': ['招商银行', '中国平安', '兴业银行', '宁波银行'],
    }
    
    # 概念板块（热门概念）
    CONCEPTS = {
        'AI': ['科大讯飞', '寒武纪', '海康威视'],
        '芯片': ['中芯国际', '韦尔股份', '北方华创'],
        '新能源汽车': ['宁德时代', '比亚迪', '亿纬锂能'],
        '医疗器械': ['迈瑞医疗', '乐普医疗', '心脉医疗'],
    }
    
    @classmethod
    def get_hot_stocks(cls, limit: int = 10) -> List[str]:
        """获取热门股票（示例）"""
        hot = [
            '603960',  # 克莱机电
            '600938',  # 中国海油
            '600329',  # 达仁堂
            '002737',  # 葵花药业
            '603639',  # 应流股份
            '300662',  # 杰恩设计
            '601006',  # 大秦铁路
        ]
        return hot[:limit]


if __name__ == "__main__":
    print("✅ 因子选股系统已加载")
    print("\n因子类型:")
    print("  - 动量因子: 近期涨幅")
    print("  - 波动率: 风险指标")
    print("  - 成交量: 活跃度")
    print("  - 趋势因子: 均线多头排列")
    print("  - 相对强弱: 跑赢大盘")
    print("\n综合评分: S/A/B/C/D 五级")
