#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
组合轮动系统
多股票组合管理，动态轮动优化收益
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime


class PortfolioRotation:
    """
    组合轮动策略
    
    原理：
    - 持有一个股票组合
    - 定期评估各股票的相对强弱
    - 卖出弱势股，买入强势股
    - 让利润奔跑，控制回撤
    """
    
    def __init__(self, 
                 max_stocks: int = 5,
                 rebalance_days: int = 20,
                 top_n: int = 3):
        """
        初始化
        
        Args:
            max_stocks: 最大持仓股票数
            rebalance_days: 多少天调仓一次
            top_n: 保留前几名强势股
        """
        self.max_stocks = max_stocks
        self.rebalance_days = rebalance_days
        self.top_n = top_n
        
    def calculate_weights(self, stock_scores: List[Dict]) -> Dict[str, float]:
        """
        根据评分计算权重
        
        强势股给予更高权重
        """
        if not stock_scores:
            return {}
        
        # 归一化分数
        total = sum(s['score'] for s in stock_scores)
        if total == 0:
            return {s['code']: 1/len(stock_scores) for s in stock_scores}
        
        weights = {}
        for s in stock_scores:
            weights[s['code']] = s['score'] / total
        
        return weights
    
    def get_rebalance_signal(self, 
                            current_holdings: Dict[str, float],
                            stock_scores: List[Dict],
                            threshold: float = 0.1) -> Dict:
        """
        获取调仓信号
        
        Args:
            current_holdings: 当前持仓 {code: weight}
            stock_scores: 股票评分列表
            threshold: 权重变化阈值
        
        Returns:
            调仓建议
        """
        # 计算目标权重
        top_stocks = stock_scores[:self.top_n]
        target_weights = self.calculate_weights(top_stocks)
        
        # 对比当前持仓
        sell_signals = []
        buy_signals = []
        
        # 卖出的股票：不在目标列表中 或 权重下降太多
        for code, weight in current_holdings.items():
            if code not in target_weights:
                sell_signals.append({
                    'code': code,
                    'reason': '不在目标持仓中',
                    'weight': weight
                })
            elif weight - target_weights.get(code, 0) > threshold:
                sell_signals.append({
                    'code': code,
                    'reason': f"权重从{weight:.1%}降至{target_weights.get(code, 0):.1%}",
                    'weight': weight
                })
        
        # 买入的股票：在目标列表中但持仓不足
        for s in top_stocks:
            code = s['code']
            if code not in current_holdings:
                buy_signals.append({
                    'code': code,
                    'name': s['name'],
                    'target_weight': target_weights[code],
                    'score': s['score']
                })
            elif current_holdings[code] < target_weights[code] - threshold:
                buy_signals.append({
                    'code': code,
                    'name': s['name'],
                    'target_weight': target_weights[code],
                    'current_weight': current_holdings[code],
                    'score': s['score']
                })
        
        # 是否需要调仓
        need_rebalance = len(sell_signals) > 0 or len(buy_signals) > 0
        
        return {
            'need_rebalance': need_rebalance,
            'current_holdings': current_holdings,
            'target_weights': target_weights,
            'sell': sell_signals,
            'buy': buy_signals,
            'reason': f'调仓信号: 卖出{len(sell_signals)}只, 买入{len(buy_signals)}只'
        }
    
    def get_rotation_signal(self, 
                           stock_performance: Dict[str, Dict],
                           momentum_period: int = 20) -> Dict:
        """
        轮动信号
        
        短期强势股轮入，弱势股轮出
        """
        # 按近期涨幅排序
        sorted_stocks = sorted(
            stock_performance.items(),
            key=lambda x: x[1].get('change_20d', 0),
            reverse=True
        )
        
        # 轮动建议
        if not sorted_stocks:
            return {'action': '持有', 'reason': '无数据'}
        
        top = sorted_stocks[0]
        bottom = sorted_stocks[-1]
        
        # 轮动信号
        if top[1].get('change_20d', 0) - bottom[1].get('change_20d', 0) > 20:
            # 差距超过20%，触发轮动
            return {
                'action': '轮动 🔄',
                'from': bottom[0],
                'to': top[0],
                'reason': f'{top[0]}近20日涨{top[1].get("change_20d", 0):.1f}%, 强于{bottom[0]}'
            }
        else:
            return {
                'action': '持有 ➡️',
                'reason': '股票表现差距不大，保持当前持仓'
            }


class RiskControl:
    """
    风险控制系统
    """
    
    @staticmethod
    def calculate_var(returns: List[float], confidence: float = 0.95) -> float:
        """
        计算VaR（Value at Risk）
        一定置信水平下的最大可能亏损
        """
        if not returns:
            return 0
        
        sorted_returns = sorted(returns)
        index = int((1 - confidence) * len(sorted_returns))
        return abs(sorted_returns[index])
    
    @staticmethod
    def calculate_max_drawdown(values: List[float]) -> Dict:
        """
        计算最大回撤
        """
        if not values:
            return {'max_drawdown': 0, 'peak': 0, 'trough': 0}
        
        peak = values[0]
        max_dd = 0
        peak_idx = 0
        trough_idx = 0
        
        for i, v in enumerate(values):
            if v > peak:
                peak = v
                peak_idx = i
            
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
                trough_idx = i
        
        return {
            'max_drawdown': max_dd * 100,
            'peak_value': peak,
            'trough_value': values[trough_idx],
            'peak_date': peak_idx,
            'trough_date': trough_idx
        }
    
    @staticmethod
    def portfolio_volatility(weights: List[float], 
                           correlations: np.ndarray,
                           volatilities: List[float]) -> float:
        """
        组合波动率
        """
        if len(weights) != len(volatilities):
            return 0
        
        # 组合方差 = w.T * Sigma * w
        weights_arr = np.array(weights)
        vol_arr = np.array(volatilities)
        
        # 简化：假设相关性矩阵正确
        portfolio_var = np.dot(weights_arr * vol_arr, 
                             np.dot(correlations, weights_arr * vol_arr))
        
        return np.sqrt(portfolio_var)
    
    @staticmethod
    def risk_alert(portfolio_value: float, 
                   max_drawdown: float,
                   daily_var: float) -> List[str]:
        """
        风险预警
        """
        alerts = []
        
        if max_drawdown > 15:
            alerts.append(f'⚠️ 最大回撤{max_drawdown:.1f}%，超过15%警戒线')
        
        if daily_var > portfolio_value * 0.05:
            alerts.append(f'⚠️ 日风险敞口{ daily_var/portfolio_value:.1%}，超过5%')
        
        return alerts


class PortfolioManager:
    """
    组合管理器
    """
    
    def __init__(self):
        self.rotation = PortfolioRotation()
        self.risk = RiskControl()
        self.positions = {}  # 当前持仓
        self.cash = 0
        self.history = []  # 调仓历史
    
    def init_portfolio(self, cash: float, initial_stocks: List[Dict]):
        """
        初始化组合
        """
        self.cash = cash
        
        # 等权分配
        weight = 1.0 / len(initial_stocks)
        for stock in initial_stocks:
            self.positions[stock['code']] = {
                'name': stock['name'],
                'weight': weight,
                'shares': 0,
                'avg_price': 0
            }
    
    def update_prices(self, prices: Dict[str, float]):
        """更新价格"""
        total_value = self.cash
        
        for code, pos in self.positions.items():
            if code in prices:
                pos['current_price'] = prices[code]
                pos['current_value'] = pos['shares'] * prices[code]
                total_value += pos['current_value']
        
        # 更新权重
        for pos in self.positions.values():
            if total_value > 0:
                pos['weight'] = pos['current_value'] / total_value
    
    def rebalance(self, target_weights: Dict[str, float], prices: Dict[str, float]):
        """
        执行调仓
        """
        # 简化：直接按目标权重调仓
        total_assets = self.cash + sum(
            p.get('current_value', 0) for p in self.positions.values()
        )
        
        # 记录调仓
        record = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'actions': []
        }
        
        for code, target_weight in target_weights.items():
            target_value = total_assets * target_weight
            current_pos = self.positions.get(code, {})
            current_value = current_pos.get('current_value', 0)
            
            diff_value = target_value - current_value
            
            if code in prices and abs(diff_value) > prices[code] * 100:
                # 交易100股
                shares = int(diff_value / prices[code] / 100) * 100
                if shares != 0:
                    record['actions'].append({
                        'code': code,
                        'action': '买入' if shares > 0 else '卖出',
                        'shares': abs(shares),
                        'price': prices[code]
                    })
                    
                    if shares > 0:
                        self.cash -= shares * prices[code]
                        current_pos['shares'] = current_pos.get('shares', 0) + shares
                        current_pos['avg_price'] = prices[code]
                    else:
                        self.cash += abs(shares) * prices[code]
                        current_pos['shares'] = max(0, current_pos.get('shares', 0) + shares)
        
        self.history.append(record)
        return record
    
    def get_status(self) -> Dict:
        """获取组合状态"""
        total_value = self.cash + sum(
            p.get('current_value', 0) for p in self.positions.values()
        )
        
        return {
            'total_value': total_value,
            'cash': self.cash,
            'positions': self.positions,
            'position_ratio': (total_value - self.cash) / total_value if total_value > 0 else 0,
            'total_positions': len([p for p in self.positions.values() if p.get('shares', 0) > 0])
        }


if __name__ == "__main__":
    print("✅ 组合轮动系统已加载")
    print("\n功能模块:")
    print("  - 组合轮动: 定期调仓，卖出弱势股买入强势股")
    print("  - 风险控制: VaR、最大回撤、风险预警")
    print("  - 组合管理: 持仓跟踪、权重计算")
