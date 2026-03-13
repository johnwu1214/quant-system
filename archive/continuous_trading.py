#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股盘中持续交易系统
持续运行，自动执行交易
"""
import sys
sys.path.insert(0, '/Users/john.wu/quant_system')

import json
import os
from datetime import datetime, time
import time

def is_trading_time():
    """检查是否在交易时间"""
    now = datetime.now()
    current_time = now.time()
    
    # 上午: 9:30-11:30
    # 下午: 13:00-15:00
    
    if now.weekday() >= 5:
        return False, "周末"
    
    if time(9, 30) <= current_time < time(11, 30):
        return True, "上午盘"
    if time(13, 0) <= current_time < time(15, 0):
        return True, "下午盘"
    
    return False, "非交易时间"

def run_continuous():
    """持续运行"""
    print("="*70)
    print("🦞 A股盘中持续交易系统 v2.0")
    print("="*70)
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("按 Ctrl+C 停止交易")
    print("="*70)
    
    round_num = 0
    
    while True:
        try:
            now = datetime.now()
            is_trading, status = is_trading_time()
            
            if is_trading:
                round_num += 1
                print(f"\n{'='*70}")
                print(f"📈 第 {round_num} 轮交易 - {status}")
                print(f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 执行交易
                import subprocess
                result = subprocess.run(
                    ['python3', 'intraday_v2.py'],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd='/Users/john.wu/quant_system'
                )
                
                # 解析输出
                output = result.stdout
                if '📊 价格' in output:
                    for line in output.split('\n'):
                        if '📊 价格' in line or '🔧 动作' in line or '💰 组合' in line or '📦 持仓' in line:
                            print(line)
                
                # 等待5分钟
                print(f"⏳ 等待下一轮...")
                time.sleep(300)  # 5分钟
                
            else:
                # 非交易时间
                if "非交易时间" in status:
                    print(f"\n😴 {status} - {now.strftime('%H:%M:%S')} - 等待中...")
                else:
                    print(f"\n📅 {status}")
                
                # 等待1分钟检查
                time.sleep(60)
                
        except KeyboardInterrupt:
            print("\n\n🛑 交易系统已停止")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_continuous()
