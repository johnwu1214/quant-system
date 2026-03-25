#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股全量历史数据下载脚本 (增强版)
增加重试机制和延时，降低请求频率
"""
import os
import sys
import time
import akshare as ak
from datetime import datetime

# 数据存储目录
DATA_DIR = os.path.expanduser("~/quant_system/data/history")
os.makedirs(DATA_DIR, exist_ok=True)

# 配置
MAX_RETRIES = 5  # 每次请求最大重试次数
RETRY_DELAY = 3   # 重试间隔(秒)
REQUEST_DELAY = 2 # 请求间隔(秒)


def get_stock_list():
    """获取A股股票列表"""
    print("📋 获取股票列表...")
    
    for attempt in range(MAX_RETRIES):
        try:
            df = ak.stock_info_a_code_name()
            stocks = []
            for _, row in df.iterrows():
                code = str(row['code'])
                if code.startswith(('6', '0', '3')):
                    stocks.append({'code': code, 'name': row['name']})
            print(f"   共有 {len(stocks)} 只A股")
            return stocks
        except Exception as e:
            print(f"   ⚠️ 尝试 {attempt+1}/{MAX_RETRIES} 失败: {str(e)[:50]}")
            time.sleep(RETRY_DELAY)
    
    return []


def download_stock(stock_code: str, stock_name: str) -> bool:
    """下载单只股票历史数据"""
    
    for attempt in range(MAX_RETRIES):
        try:
            # 转换代码格式
            symbol = stock_code
            
            # 获取历史数据
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date="20200101",
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust="qfq"
            )
            
            if df is not None and len(df) > 0:
                filename = f"{DATA_DIR}/{stock_code}_{stock_name}.csv"
                df.to_csv(filename, index=False, encoding='utf-8-sig')
                return True
                
        except Exception as e:
            err_msg = str(e)[:50]
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))  # 递增延时
            else:
                print(f"   ❌ {stock_name} ({stock_code}): {err_msg}")
    
    return False


def download_batch(stocks: list):
    """批量下载"""
    total = len(stocks)
    success = 0
    failed = []
    
    print(f"\n🚀 开始下载 {total} 只股票...")
    print(f"⏱️ 预计时间: {total * REQUEST_DELAY / 60:.0f} 分钟")
    print("-" * 50)
    
    start_time = time.time()
    
    for i, stock in enumerate(stocks):
        code = stock['code']
        name = stock['name']
        
        # 进度
        if (i + 1) % 50 == 0:
            elapsed = time.time() - start_time
            eta = (elapsed / (i + 1)) * (total - i - 1)
            print(f"📊 进度: {i+1}/{total} ({100*(i+1)/total:.1f}%) - 成功: {success} - 预计剩余: {eta/60:.1f}分钟")
        
        # 下载
        if download_stock(code, name):
            success += 1
        
        # 延时
        time.sleep(REQUEST_DELAY)
    
    print("-" * 50)
    print(f"✅ 完成: {success}/{total} 只成功")
    
    return success, failed


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════╗
║    A股全量历史数据下载器 (增强版)                  ║
║    重试机制 + 降低请求频率                         ║
╚══════════════════════════════════════════════════════╝
    """)
    
    # 获取股票列表
    stocks = get_stock_list()
    if not stocks:
        print("❌ 无法获取股票列表")
        sys.exit(1)
    
    # 下载
    success, failed = download_batch(stocks)
    
    print(f"\n🎉 下载完成!")
    print(f"   成功: {success} 只")
    print(f"   路径: {DATA_DIR}")
