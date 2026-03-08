#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tushare Pro 数据下载脚本
获取A股全部历史数据
"""
import os
import sys
import time
import tushare as ts
from datetime import datetime

# 设置你的Tushare Token
# 方法1: 环境变量
TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")

# 方法2: 直接填写(不推荐泄露)
# TUSHARE_TOKEN = "your_token_here"

# 数据存储目录
DATA_DIR = os.path.expanduser("~/quant_system/data/history")
os.makedirs(DATA_DIR, exist_ok=True)


def init_tushare():
    """初始化Tushare"""
    if not TUSHARE_TOKEN:
        print("❌ 请设置 TUSHARE_TOKEN")
        print("   方法1: export TUSHARE_TOKEN='你的token'")
        print("   方法2: 编辑脚本填入token")
        return None
    
    try:
        pro = ts.pro_api(TUSHARE_TOKEN)
        # 测试连接
        df = pro.trade_cal(exchange='SSE', start_date='20260101', end_date='20260102')
        print(f"✅ Tushare 连接成功!")
        return pro
    except Exception as e:
        print(f"❌ Tushare 连接失败: {e}")
        return None


def get_stock_list(pro):
    """获取A股股票列表"""
    print("📋 获取股票列表...")
    
    try:
        # 获取全部A股
        df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date')
        
        stocks = []
        for _, row in df.iterrows():
            code = row['symbol']
            # 只保留A股 (6开头沪市, 0/3开头深市)
            if code.startswith(('6', '0', '3')):
                stocks.append({
                    'code': code,
                    'name': row['name'],
                    'ts_code': row['ts_code'],
                    'list_date': row['list_date']
                })
        
        print(f"   共有 {len(stocks)} 只A股")
        return stocks
        
    except Exception as e:
        print(f"❌ 获取股票列表失败: {e}")
        return []


def download_stock_daily(pro, stock_code: str, ts_code: str) -> bool:
    """下载单只股票历史K线"""
    try:
        # 上市日期
        start_date = '20000101'
        
        # 尝试获取数据
        df = pro.daily(
            ts_code=ts_code,
            start_date=start_date,
            end_date=datetime.now().strftime('%Y%m%d')
        )
        
        if df is not None and len(df) > 0:
            # 按日期排序
            df = df.sort_values('trade_date')
            
            # 保存为CSV
            filename = f"{DATA_DIR}/{stock_code}.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            return True
            
    except Exception as e:
        pass
    
    return False


def download_batch(pro, stocks: list, delay: float = 0.2):
    """批量下载"""
    total = len(stocks)
    success = 0
    failed = []
    
    print(f"\n🚀 开始下载 {total} 只股票历史数据...")
    print(f"📁 保存位置: {DATA_DIR}")
    print(f"⏱️ 预计时间: {total * 3 / 60:.0f} 分钟")
    print("-" * 50)
    
    for i, stock in enumerate(stocks):
        code = stock['code']
        name = stock['name']
        ts_code = stock['ts_code']
        
        # 进度
        if (i + 1) % 100 == 0:
            print(f"📊 进度: {i+1}/{total} ({100*(i+1)/total:.1f}%) - 成功: {success}")
        
        # 下载
        if download_stock_daily(pro, code, ts_code):
            success += 1
        else:
            failed.append(code)
        
        # 延时防限流
        time.sleep(delay)
    
    print("-" * 50)
    print(f"✅ 下载完成: {success}/{total} 只成功")
    
    if failed:
        print(f"❌ 失败: {len(failed)} 只")
        print(f"   前10个: {failed[:10]}")
    
    return success, failed


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════╗
║         Tushare Pro A股数据下载器                   ║
╚══════════════════════════════════════════════════════╝
    """)
    
    if not TUSHARE_TOKEN:
        print("""
⚠️  请先设置 Tushare Token:

1. 访问 https://tushare.pro 注册
2. 获取 Token
3. 设置: export TUSHARE_TOKEN='你的token'
4. 重新运行脚本

或修改脚本直接填入token
        """)
        sys.exit(1)
    
    # 初始化
    pro = init_tushare()
    if not pro:
        sys.exit(1)
    
    # 获取股票列表
    stocks = get_stock_list(pro)
    if not stocks:
        print("❌ 无股票数据")
        sys.exit(1)
    
    # 下载
    success, failed = download_batch(pro, stocks)
    
    print(f"\n🎉 下载完成!")
    print(f"   成功: {success} 只")
    print(f"   失败: {len(failed)} 只")
    print(f"   路径: {DATA_DIR}")
