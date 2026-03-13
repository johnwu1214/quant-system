#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib 量化投资工作流示例
基于官方教程配置
"""
import qlib
import os
from qlib.config import REG_CN

# 配置
provider_uri = os.path.expanduser("~/.qlib/qlib_data/cn_data")

# 检查数据是否存在
if not os.path.exists(provider_uri):
    print("""
❌ 数据目录不存在: {}
   
请先下载数据:
   
方法1: 使用官方脚本
   cd ~/miniconda3/lib/python3.13/site-packages/qlib
   python scripts/get_data.py qlib_data --target_dir {} --region cn

方法2: 手动下载
   访问: https://github.com/microsoft/qlib/tree/main/data
   下载 cn_data 压缩包
   解压到: {}

""".format(provider_uri, provider_uri, provider_uri))
    exit(1)

# 初始化
qlib.init(provider_uri=provider_uri, region=REG_CN)

from qlib.data import D

print("""
╔══════════════════════════════════════════════════════╗
║         Qlib 量化投资工作流                       ║
╚══════════════════════════════════════════════════════╝
""")

# 测试获取数据
print("📊 测试获取数据...")

# 获取交易日历
calendar = D.calendar(start_time='2025-01-01', end_time='2026-03-01')
print(f"✅ 交易日历: {len(calendar)} 天")

# 获取沪深300成分股
instruments = D.instruments(market='csi300')
stock_list = D.list_instruments(instruments=instruments, start_time='2025-01-01', end_time='2026-03-01', as_list=True)
print(f"✅ 沪深300股票: {len(stock_list)} 只")

# 获取股票数据
fields = ['close', 'open', 'volume']
data = D.features(['sh.600519'], fields, '2025-01-01', '2026-03-01')
print(f"✅ 茅台数据: {len(data)} 条")

print("""
📈 Qlib 工作流配置示例:

1. 模型: LGBModel (LightGBM)
2. 数据: Alpha158 因子库
3. 策略: TopkDropoutStrategy
4. 回测: 2008-2020

详细配置请参考官方YAML文件
""")
