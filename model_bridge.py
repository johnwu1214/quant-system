#!/usr/bin/env python3
"""
model_bridge.py — Qlib选股结果 → intraday watch_list自动更新
每天收盘后运行一次，用中期动量因子筛选候选股，写入watch_list.json
"""
import json, os, sys
from datetime import datetime, date
import pandas as pd
import numpy as np

QLIB_DATA_PATH = "/root/.qlib/qlib_data/cn_data_community"
OUTPUT_PATH    = "/root/quant-system/watch_list.json"
UNIVERSE       = "csi300"
TOP_N          = 20
LOOKBACK_DAYS  = 250
SKIP_DAYS      = 20
MIN_PRICE      = 5.0
MAX_PRICE      = 200.0

try:
    import qlib
    from qlib.constant import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=QLIB_DATA_PATH, region=REG_CN)
    print("✅ Qlib初始化成功")
except Exception as e:
    print(f"❌ Qlib初始化失败: {e}")
    sys.exit(1)

cal       = D.calendar(freq="day")
today     = pd.Timestamp(date.today())
past_cal  = [c for c in cal if c <= today]
if not past_cal:
    print("❌ 无有效交易日")
    sys.exit(1)
latest_date = past_cal[-1]
print(f"📅 最新交易日: {latest_date.strftime('%Y-%m-%d')}")

print(f"📊 加载{UNIVERSE}因子数据...")
try:
    instruments = D.instruments(UNIVERSE)
    df = D.features(
        instruments,
        fields=[
            "$close",
            f"Ref($close,{SKIP_DAYS})/Ref($close,{LOOKBACK_DAYS})-1",
            "Sub(0, $close/Ref($close,20)-1)",
        ],
        start_time="2024-01-01",
        end_time=str(latest_date.date()),
        freq="day"
    )
    df.columns = ["close", "mom_mid", "reversal"]
    df.index.names = ["instrument", "datetime"]
    df = df.dropna()
    print(f"✅ 数据加载: {len(df):,}条")
except Exception as e:
    print(f"❌ 数据加载失败: {e}")
    sys.exit(1)

close_wide = df["close"].unstack(level=0)
mom_wide   = df["mom_mid"].unstack(level=0)
rev_wide   = df["reversal"].unstack(level=0)
signal_date = close_wide.index.sort_values()[-1]
print(f"📈 信号日期: {signal_date.strftime('%Y-%m-%d')}")

mom_cross = mom_wide.loc[signal_date].dropna()
rev_cross = rev_wide.loc[signal_date].dropna()
cls_cross = close_wide.loc[signal_date].dropna()

valid_stocks = cls_cross[(cls_cross >= MIN_PRICE) & (cls_cross <= MAX_PRICE)].index
mom_cross = mom_cross.reindex(valid_stocks).dropna()
rev_cross = rev_cross.reindex(valid_stocks).dropna()

def zscore(s):
    return (s - s.mean()) / (s.std() + 1e-8)

common = mom_cross.index.intersection(rev_cross.index)
if len(common) < TOP_N:
    print(f"❌ 有效股票数不足: {len(common)}")
    sys.exit(1)

mom_z = zscore(mom_cross.reindex(common))
rev_z = zscore(rev_cross.reindex(common))
combo_score = mom_z * 0.7 + rev_z * 0.3
top_stocks  = combo_score.nlargest(TOP_N)

print(f"\n{'排名':<4} {'代码':<12} {'得分':>7} {'中期动量':>9} {'反转':>8} {'价格':>7}")
print("-" * 52)
for rank, (stock, score) in enumerate(top_stocks.items(), 1):
    m = mom_cross.get(stock, 0)
    r = rev_cross.get(stock, 0)
    p = cls_cross.get(stock, 0)
    print(f"{rank:<4} {stock:<12} {score:>7.3f} {m*100:>8.1f}% {r*100:>7.1f}% {p:>7.2f}")

watch_list = {
    "updated_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "signal_date": signal_date.strftime("%Y-%m-%d"),
    "universe":    UNIVERSE,
    "method":      "中期动量250d跳20d(70%) + 反转因子20d(30%)",
    "top_n":       TOP_N,
    "stocks": [
        {
            "symbol":   stock[2:] if stock[:2] in ("SH","SZ","BJ") else stock,
            "score":    round(float(score), 4),
            "mom_mid":  round(float(mom_cross.get(stock, 0)), 4),
            "reversal": round(float(rev_cross.get(stock, 0)), 4),
            "price":    round(float(cls_cross.get(stock, 0)), 2),
            "rank":     rank
        }
        for rank, (stock, score) in enumerate(top_stocks.items(), 1)
    ]
}

# ── 合并 stock_selector_v2 的结果 ──────────────────────
import os
selector_codes = []
selector_meta  = {}
if os.path.exists(OUTPUT_PATH):
    try:
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            old_data = json.load(f)
        # 兼容 stock_selector 格式
        if "watch_list" in old_data:
            selector_codes = old_data["watch_list"][:10]  # 最多取前10只
            selector_meta  = {
                "market_regime": old_data.get("market_regime", "unknown"),
                "market_ret30":  old_data.get("market_ret30", 0),
                "mode":          old_data.get("mode", "unknown"),
            }
            print(f"📊 合并stock_selector结果: {len(selector_codes)}只")
            print(f"   市场状态: {selector_meta.get('market_regime')} | 模式: {selector_meta.get('mode')}")
    except Exception as e:
        print(f"⚠️ 读取旧watch_list失败: {e}")

# 合并两个列表（Qlib优先，selector补充）
qlib_codes = [s["symbol"] for s in watch_list["stocks"]]
merged_codes = list(dict.fromkeys(qlib_codes + selector_codes))  # 去重保序

# 补充selector独有的股票到末尾
extra = [c for c in selector_codes if c not in qlib_codes]
if extra:
    print(f"📌 stock_selector补充: {extra}")

watch_list["selector_meta"]   = selector_meta
watch_list["selector_codes"]  = selector_codes
watch_list["merged_total"]    = len(merged_codes)
watch_list["source"] = "model_bridge(Qlib因子) + stock_selector_v2(基本面)"

# 把merged_codes写入watch_list字段供load_watch_list读取
# 同时保留stocks字段供详细分析
watch_list["watch_list"] = merged_codes

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(watch_list, f, ensure_ascii=False, indent=2)

print(f"\n💾 已写入: {OUTPUT_PATH}")
print(f"✅ 完成！Qlib:{len(qlib_codes)}只 + Selector补充:{len(extra)}只 = 合并:{len(merged_codes)}只")
if selector_meta:
    print(f"📈 市场状态: {selector_meta.get('market_regime')} | {selector_meta.get('mode')}")
