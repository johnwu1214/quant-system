#!/usr/bin/env python3
"""
数据验证脚本 - 验证历史日线数据是否充足
用法: python3 validate_data.py
"""
import baostock as bs
import pandas as pd
from datetime import datetime, timedelta

bs.login()

symbols = {
    '603960': 'sh.603960',
    '600938': 'sh.600938', 
    '600329': 'sh.600329',
    '002737': 'sz.002737'
}

end_date = datetime.today().strftime('%Y-%m-%d')
start_date = (datetime.today() - timedelta(days=90)).strftime('%Y-%m-%d')

print(f"数据验证报告 | {end_date}")
print("="*50)

all_ok = True
for name, code in symbols.items():
    rs = bs.query_history_k_data_plus(
        code, "date,close,volume",
        start_date=start_date,
        end_date=end_date,
        frequency="d", adjustflag="3"
    )
    df = rs.get_data()
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df = df.dropna()
    days = len(df)
    
    status = "✅" if days >= 52 else "⚠️ 数据不足"
    if days < 52:
        all_ok = False
    print(f"{status} {name}: {days}天 | 最新价¥{df['close'].iloc[-1]:.2f}")

print("="*50)
if all_ok:
    print("✅ 所有股票数据充足，可以明天开盘测试")
else:
    print("⚠️ 有股票数据不足52天，MACD计算结果不可靠！")
    print(" 建议扩大 start_date 到180天前再试")

bs.logout()
