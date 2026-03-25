#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据更新脚本
将MomaAPI获取的最新数据更新到量化系统
"""
import os
import sys
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import get_stock_daily, get_stock_realtime

# 数据存储目录
DATA_DIR = os.path.expanduser("~/quant_system/data")

def update_latest_data(stock_codes: list = None):
    """更新最新数据"""
    
    if stock_codes is None:
        # 默认更新持仓股票
        stock_codes = ['600519', '600036', '603960', '600938', '600329', '002737']
    
    print(f"📥 更新最新数据 ({len(stock_codes)} 只股票)...")
    print("="*50)
    
    updated = []
    failed = []
    
    for code in stock_codes:
        try:
            # 获取日线数据
            df = get_stock_daily(code, 3)
            
            if df is not None and len(df) > 0:
                # 保存到文件
                filename = f"{DATA_DIR}/{code}.csv"
                
                # 读取已有数据
                existing = pd.read_csv(filename) if os.path.exists(filename) else pd.DataFrame()
                
                # 合并数据
                if not existing.empty:
                    # 去重合并
                    combined = pd.concat([existing, df])
                    combined = combined.drop_duplicates(subset=['date'], keep='last')
                    combined = combined.sort_values('date')
                else:
                    combined = df
                
                # 保存
                combined.to_csv(filename, index=False, encoding='utf-8')
                
                latest = df.iloc[-1]
                updated.append({
                    'code': code,
                    'date': latest['date'],
                    'close': latest['close']
                })
                print(f"  ✅ {code}: {latest['date']} ¥{latest['close']:.2f}")
            else:
                failed.append(code)
                print(f"  ❌ {code}: 无数据")
                
        except Exception as e:
            failed.append(code)
            print(f"  ❌ {code}: {str(e)[:30]}")
    
    print("="*50)
    print(f"✅ 成功: {len(updated)} 只")
    print(f"❌ 失败: {len(failed)} 只")
    
    return updated, failed


def get_realtime_prices(stock_codes: list = None):
    """获取实时行情"""
    
    if stock_codes is None:
        stock_codes = ['600519', '600036', '603960', '600938', '600329', '002737']
    
    print("\n📈 实时行情:")
    print("="*50)
    
    prices = {}
    for code in stock_codes:
        try:
            rt = get_stock_realtime(code)
            if rt:
                price = rt.get('price', 0)
                change = rt.get('change_pct', 0)
                prices[code] = {'price': price, 'change_pct': change}
                print(f"  {code}: ¥{price:.2f} ({change:+.2f}%)")
        except Exception as e:
            print(f"  {code}: 获取失败")
    
    return prices


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='更新股票数据')
    parser.add_argument('--codes', nargs='+', help='股票代码列表')
    parser.add_argument('--realtime', action='store_true', help='获取实时行情')
    
    args = parser.parse_args()
    
    if args.realtime:
        get_realtime_prices(args.codes)
    else:
        update_latest_data(args.codes)
