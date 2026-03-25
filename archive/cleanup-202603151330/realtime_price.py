#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实价格获取 - 东方财富网页抓取
"""
import re
import json

def get_realtime_price_eastmoney(code):
    """从东方财富获取实时价格"""
    try:
        # 转换代码格式
        if code.startswith('6'):
            market = '1'  # 上海
            full_code = f'1.{code}'
        else:
            market = '0'  # 深圳
            full_code = f'0.{code}'
        
        import urllib.request
        url = f'https://push2.eastmoney.com/api/qt/stock/get?secid={full_code}&fields=f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f57,f58,f59,f60,f116,f117,f162,f167,f168,f169,f170,f171,f173,f177'
        
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        if data.get('data'):
            price = data['data'].get('f43', 0) / 1000  # 价格需要除以1000
            return price
    except Exception as e:
        pass
    
    return None

def get_multiple_prices(codes):
    """获取多只股票价格"""
    prices = {}
    
    for code in codes:
        price = get_realtime_price_eastmoney(code)
        if price:
            prices[code] = round(price, 2)
    
    return prices

if __name__ == "__main__":
    # 测试
    codes = ['603960', '600938', '600329', '002737']
    prices = get_multiple_prices(codes)
    print("实时价格:")
    for code, price in prices.items():
        print(f"  {code}: ¥{price}")
