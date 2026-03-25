import sys, json, datetime
sys.path.insert(0, '/root/quant-system')
from data_manager import get_realtime_price

positions = {
    '300394': {'cost': 285.80, 'stop': 283.39, 'name': '天孚通信'},
    '300502': {'cost': 468.00, 'stop': 447.56, 'name': '新易盛'},
    '600089': {'cost': 28.61,  'stop': 25.51,  'name': '特变电工'},
    '601888': {'cost': 74.59,  'stop': 67.52,  'name': '中国中免'},
}
cash = 12477.48
total = cash

print(f"=== PROMETHEUS {datetime.datetime.now().strftime('%H:%M:%S')} ===")
print(f"{'代码':<8}{'名称':<8}{'现价':>8}{'今日':>8}{'浮盈':>8}{'止损距':>8}  ")
print("-" * 54)

for code, info in positions.items():
    raw = get_realtime_price(code)
    cur = raw.get('price') if isinstance(raw, dict) else raw
    chg = raw.get('change_pct', 0) if isinstance(raw, dict) else 0
    pnl = (cur - info['cost']) / info['cost'] * 100
    safe = (cur - info['stop']) / cur * 100
    total += cur * 100
    flag = '🔴' if safe < 3 else ('⚠️' if safe < 6 else '✅')
    print(f"{code:<8}{info['name']:<8}{cur:>8.2f}{chg:>+8.2f}{pnl:>+8.2f}{safe:>7.1f}% {flag}")

print("-" * 54)
nav = total / 100000
print(f"现金 ¥{cash:,.2f} | 总资产 ¥{total:,.2f} | 净值 {nav:.4f}")
print(f"今日盈亏 ¥{total - 100000:+,.2f}")
print()
print("--- 最新交易日志 ---")
import subprocess
r = subprocess.run(['tail','-5','/root/quant-system/logs/trading_20260323.log'],
                   capture_output=True, text=True)
print(r.stdout)
