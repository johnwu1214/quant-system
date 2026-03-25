#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股实时价格获取 - tushare接口
稳定获取实时行情
"""
import tushare as ts
from typing import Dict, Optional
import warnings
warnings.filterwarnings('ignore')

def get_realtime_prices(codes: list = None) -> Dict[str, float]:
    """
    获取实时股票价格
    
    Args:
        codes: 股票代码列表，如 ['603960', '600938']
        
    Returns:
        Dict: {code: price}
    """
    if codes is None:
        codes = ['603960', '600938', '600329', '002737']
    
    prices = {}
    
    try:
        # tushare不需要token即可获取实时行情
        df = ts.get_realtime_quotes(codes)
        
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                code = row['code']
                price = float(row['price'])
                prices[code] = price
                
    except Exception as e:
        print(f"获取实时价格失败: {e}")
        # 备用: 逐个获取
        for code in codes:
            try:
                df = ts.get_realtime_quotes(code)
                if df is not None and not df.empty:
                    prices[code] = float(df.iloc[0]['price'])
            except:
                pass
    
    return prices


def get_stock_info(code: str) -> dict:
    """获取股票详细信息"""
    try:
        df = ts.get_realtime_quotes(code)
        if df is not None and not df.empty:
            row = df.iloc[0]
            return {
                'code': row['code'],
                'name': row['name'],
                'price': float(row['price']),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'pre_close': float(row['pre_close']),
                'change': float(row['change']),
                'pct_chg': float(row['pct_chg']),
                'volume': float(row['volume']),
                'amount': float(row['amount']),
                'time': row['time']
            }
    except Exception as e:
        print(f"获取股票信息失败: {e}")
    
    return {}


if __name__ == "__main__":
    # 测试
    print("=== 实时行情测试 ===")
    codes = ['603960', '600938', '600329', '002737']
    prices = get_realtime_prices(codes)
    
    print("\n实时价格:")
    for code, price in prices.items():
        info = get_stock_info(code)
        name = info.get('name', code)
        change = info.get('change', 0)
        pct = info.get('pct_chg', 0)
        print(f"  {code} {name}: ¥{price:+.2f} ({change:+.2f}, {pct:+.2f}%)")
