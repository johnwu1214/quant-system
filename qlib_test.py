#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib 策略测试 - 使用LightGBM + Alpha158因子
"""
import qlib
import os
from qlib.config import REG_CN

# 初始化
provider_uri = os.path.expanduser("~/.qlib/qlib_data/cn_data")
qlib.init(provider_uri=provider_uri, region=REG_CN)

print("""
╔══════════════════════════════════════════════════════╗
║         Qlib 策略测试 - LightGBM               ║
╚══════════════════════════════════════════════════════╝
""")

# 导入必要模块
from qlib.data import D
from qlib.contrib.model.gbdt import LGBModel
from qlib.contrib.strategy import TopkDropoutStrategy
from qlib.contrib.evaluate import backtest
import pandas as pd

# 1. 获取数据
print("\n📊 1. 获取沪深300数据...")

instruments = D.instruments("csi300")
stock_list = D.list_instruments(instruments=instruments, start_time="2020-01-01", end_time="2025-12-31", as_list=True)
print(f"   沪深300股票: {len(stock_list)} 只")

# 2. 获取特征数据
print("\n📈 2. 获取特征数据...")

fields = [
    "$close", "$open", "$high", "$low", "$volume",
    "Ref($close, 1)/Ref($close, 2)-1",  # 1日收益率
    "Ref($close, 5)/Ref($close, 10)-1",  # 5日收益率
]

# 获取2020-2024数据
data = D.features(
    instruments=stock_list[:50],  # 取50只股票测试
    fields=fields,
    start_time="2020-01-01",
    end_time="2024-12-31"
)
print(f"   数据形状: {data.shape}")

# 3. 简单回测
print("\n🎯 3. 简单回测...")

# 获取最近一年数据作为测试
test_data = D.features(
    instruments=stock_list[:50],
    fields=["$close"],
    start_time="2025-01-01",
    end_time="2025-12-31"
)

if test_data is not None and len(test_data) > 0:
    # 简单策略：每月初买入上月涨幅前5的股票
    print(f"   回测数据: {len(test_data)} 条")
    
    # 计算收益率
    returns = test_data["$close"].pct_change().dropna()
    print(f"   平均日收益率: {returns.mean()*100:.4f}%")
    
print("\n✅ Qlib 工作流测试完成!")
print("""
📋 下一步:
   1. 使用完整Alpha158因子库
   2. 训练LightGBM模型
   3. 执行完整回测
""")
