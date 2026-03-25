#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股全量历史数据下载脚本
使用 AkShare 获取全部A股历史数据
"""
import os
import sys
import time
import akshare as ak
from datetime import datetime

# 数据存储目录
DATA_DIR = os.path.expanduser("~/quant_system/data/history")
os.makedirs(DATA_DIR, exist_ok=True)

def get_stock_list():
    """获取A股全部股票列表"""
    print("📋 获取股票列表...")
    df = ak.stock_info_a_code_name()
    stocks = []
    for _, row in df.iterrows():
        code = str(row['code'])
        name = str(row['name'])
        # 过滤A股 (6开头沪市, 0/3开头深市)
        if code.startswith(('6', '0', '3')):
            stocks.append({'code': code, 'name': name})
    return stocks

def download_stock_daily(stock_code: str, name: str, max_retries: int = 3) -> bool:
    """下载单只股票历史数据"""
    for attempt in range(max_retries):
        try:
            # 转换代码格式
            symbol = f"{stock_code}.SH" if stock_code.startswith('6') else f"{stock_code}.SZ"
            
            # 获取历史数据 (前复权, 2000-01-01至今)
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date="20000101",
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust="qfq"
            )
            
            if df is not None and len(df) > 0:
                # 保存为CSV
                filename = f"{DATA_DIR}/{stock_code}_{name}.csv"
                df.to_csv(filename, index=False, encoding='utf-8-sig')
                return True
                
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)  # 失败后等待
            else:
                print(f"  ⚠️ {name} ({stock_code}): {str(e)[:50]}")
    return False

def download_batch(stock_list: list, batch_size: int = 100, delay: float = 1.0):
    """批量下载"""
    total = len(stock_list)
    success = 0
    failed = []
    
    print(f"\n🚀 开始下载 {total} 只股票历史数据...")
    print(f"📁 保存位置: {DATA_DIR}")
    print(f"⏱️ 预计时间: {total * 2 / 60:.0f} 分钟 (按2秒/只估算)")
    print("-" * 50)
    
    for i, stock in enumerate(stock_list):
        code = stock['code']
        name = stock['name']
        
        # 进度显示
        if (i + 1) % 50 == 0:
            print(f"📊 进度: {i+1}/{total} ({100*(i+1)/total:.1f}%)")
        
        # 下载
        if download_stock_daily(code, name):
            success += 1
        else:
            failed.append(code)
        
        # 延时防封
        time.sleep(delay)
    
    print("-" * 50)
    print(f"✅ 下载完成: {success}/{total} 只成功")
    if failed:
        print(f"❌ 失败: {len(failed)} 只")
    
    return success, failed


def download_index_data():
    """下载主要指数历史数据"""
    indices = {
        "000001": "上证指数",
        "000300": "沪深300",
        "399001": "深证成指",
        "399006": "创业板指",
        "000016": "上证50",
        "000905": "中证500",
    }
    
    print("\n📈 下载指数数据...")
    
    for code, name in indices.items():
        try:
            symbol = f"sh{code}" if code.startswith('0') else f"sz{code}"
            df = ak.stock_zh_index_daily(symbol=f"sh{code}")
            if df is not None:
                filename = f"{DATA_DIR}/index_{code}_{name}.csv"
                df.to_csv(filename, index=False, encoding='utf-8-sig')
                print(f"  ✅ {name}: {len(df)} 条")
        except Exception as e:
            print(f"  ❌ {name}: {e}")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════╗
║         A股全量历史数据下载器                        ║
║         数据源: AkShare                              ║
╚══════════════════════════════════════════════════════╝
    """)
    
    # 获取股票列表
    stocks = get_stock_list()
    print(f"📋 A股股票总数: {len(stocks)} 只")
    
    # 下载指数
    download_index_data()
    
    # 开始下载
    print(f"\n🚀 开始下载 {len(stocks)} 只股票历史数据...")
    success, failed = download_batch(stocks)
    
    print("\n💡 使用说明:")
    print("   1. 运行: python3 download_all.py")
    print("   2. 数据将保存在: ~/quant_system/data/history/")
    print("   3. 每天凌晨可增量更新")
