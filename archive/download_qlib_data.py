#!/usr/bin/env python3
"""
Qlib数据下载脚本
下载A股历史数据到本地
"""
import os
import sys

# 数据目录
DATA_DIR = os.path.expanduser("~/.qlib/qlib_data/cn_data")
os.makedirs(DATA_DIR, exist_ok=True)

print("""
╔══════════════════════════════════════════════════════╗
║         Qlib A股数据下载器                        ║
╚══════════════════════════════════════════════════════╝
""")

print(f"📁 数据将保存到: {DATA_DIR}")
print("""
下载方式：
1. 自动下载（推荐）- qlib自动下载
2. 手动下载 - 从百度网盘下载

自动下载命令：
""")

# 尝试使用qlib自带的下载功能
try:
    # 检查是否有qlib.data
    from qlib.data import ops
    
    print("✅ qlib.data 模块可用")
    print("\n尝试获取数据...")
    
    # 尝试获取沪深300数据
    instruments = ["sh.600519", "sh.600036"]
    
    from qlib.data import D
    
    # 尝试获取数据
    fields = ["$close", "$open", "$high", "$low", "$volume"]
    
    for inst in instruments[:1]:
        try:
            data = D.features(inst, fields, "2025-01-01", "2025-03-01")
            print(f"✅ {inst}: {len(data)} 条")
        except Exception as e:
            print(f"❌ {inst}: {e}")
            
except Exception as e:
    print(f"⚠️ qlib.data 需要额外配置: {e}")
    print("""
请手动下载：

1. 访问 Qlib 数据页面:
   https://github.com/microsoft/qlib/tree/main/data

2. 下载 cn_data 目录:
   - 百度网盘/Google Drive

3. 解压到:
   ~/.qlib/qlib_data/
    """)

print("""
或者运行完整初始化:
python -c "import qlib; qlib.init()"
""")
