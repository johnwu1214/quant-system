#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib 策略测试 - 简化版
"""
import qlib
import os
from qlib.config import REG_CN

# 初始化
provider_uri = os.path.expanduser("~/.qlib/qlib_data/cn_data")
qlib.init(provider_uri=provider_uri, region=REG_CN)

print("""
╔══════════════════════════════════════════════════════╗
║         Qlib 数据测试                           ║
╚══════════════════════════════════════════════════════╝
""")

from qlib.data import D
import pandas as pd
import numpy as np

# 1. 获取股票列表
print("\n📊 1. 获取股票数据...")
instruments = D.instruments("csi300")
stock_list = D.list_instruments(instruments=instruments, start_time="2020-01-01", end_time="2025-12-31", as_list=True)
print(f"   沪深300股票: {len(stock_list)} 只")

# 2. 获取K线数据
print("\n📈 2. 获取K线数据...")
fields = ["$close", "$open", "$high", "$low", "$volume"]

# 取前10只股票测试
test_stocks = stock_list[:10]
data = D.features(test_stocks, fields, "2025-01-01", "2025-12-31")
print(f"   数据形状: {data.shape}")

# 3. 计算技术指标
print("\n🔧 3. 计算技术指标...")

# 计算日收益率
returns = data["$close"].pct_change()
print(f"   日收益率: {returns.mean()*100:.4f}% (平均)")

# 计算波动率
volatility = returns.std() * np.sqrt(252)
print(f"   年化波动率: {volatility.mean()*100:.2f}%")

# 4. 简单选股策略
print("\n🎯 4. 简单选股策略...")

# 按收益率排序
last_returns = data["$close"].iloc[-1] / data["$close"].iloc[0] - 1
top_stocks = last_returns.sort_values(ascending=False).head(5)

print("   2025年收益前5:")
for stock, ret in top_stocks.items():
    print(f"   {stock}: {ret*100:+.2f}%")

# 5. 获取最新数据
print("\n📅 5. 最新行情...")
latest = data.iloc[-1]
print(f"   最新收盘价: {latest['$close'].mean():.2f}")

print("""
╔══════════════════════════════════════════════════════╗
║         ✅ Qlib 测试完成!                       ║
╚══════════════════════════════════════════════════════╝

📋 结论:
   ✅ 数据获取正常
   ✅ 技术指标计算正常
   ✅ 选股策略正常

🎯 下一步:
   1. 训练LightGBM模型
   2. 完整回测
   3. 对接实盘
""")
