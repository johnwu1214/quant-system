#!/usr/bin/env python3
"""
Qlib A股数据下载脚本
基于官方教程: python scripts/get_data.py
"""
import os
import sys
import subprocess

# 数据目录
DATA_DIR = os.path.expanduser("~/.qlib/qlib_data/cn_data")
os.makedirs(DATA_DIR, exist_ok=True)

# 尝试找到Qlib脚本
qlib_paths = [
    os.path.expanduser("~/miniconda3/lib/python3.13/site-packages/qlib/scripts/get_data.py"),
    "/Users/john.wu/miniconda3/lib/python3.13/site-packages/qlib/scripts/get_data.py",
]

script_path = None
for path in qlib_paths:
    if os.path.exists(path):
        script_path = path
        break

if not script_path:
    # 搜索
    import subprocess
    result = subprocess.run(["find", os.path.expanduser("~"), "-name", "get_data.py", "-path", "*qlib*"], 
                          capture_output=True, text=True, timeout=30)
    if result.stdout:
        script_path = result.stdout.strip().split('\n')[0]

print(f"""
╔══════════════════════════════════════════════════════╗
║         Qlib A股数据下载器                      ║
╚══════════════════════════════════════════════════════╝
""")

print(f"📁 目标目录: {DATA_DIR}")

if script_path:
    print(f"📜 找到脚本: {script_path}")
    print(f"""
⚠️  警告: 下载数据约 10GB，可能需要 30-60 分钟

继续下载请输入: python {script_path} qlib_data --target_dir {DATA_DIR} --region cn
""")
else:
    print("""
⚠️ 未找到下载脚本，请手动下载:

1. 访问: https://github.com/microsoft/qlib/tree/main/data
2. 下载 cn_data 压缩包
3. 解压到: ~/.qlib/qlib_data/

或使用镜像:
- 百度网盘
- Hugging Face: huggingface.co/datasets)
""")

# 尝试直接用Python下载
print("""
或者尝试直接运行以下命令:

cd ~/miniconda3/lib/python3.13/site-packages/qlib
python scripts/get_data.py qlib_data --target_dir ~/.qlib/qlib_data/cn_data --region cn
""")
