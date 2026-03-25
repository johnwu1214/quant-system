"""
risk_manager_v2.py — ATR 动态止损模块
两道保险：ATR动态止损 + 8%硬性止损
触发止损时自动将股票加入黑名单
"""
import json, os
from datetime import datetime

try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False

import blacklist_manager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_PATH = os.path.join(BASE_DIR, 'portfolio_state.json')

ATR_PERIOD = 14
ATR_MULTIPLIER = 2.0
MAX_LOSS_RATIO = 0.08  # 8% 硬性止损

def load_portfolio():
    with open(PORTFOLIO_PATH, encoding='utf-8') as f:
        return json.load(f)

def get_kline(code, days=30):
    """获取K线数据 - 优先使用data_manager本地Qlib数据"""
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from data_manager import get_history_kline as _dm_kline
        klines = _dm_kline(code, days)
        if klines and len(klines) >= 10:
            return klines
    except Exception as e:
        pass
    if not HAS_AKSHARE:
        return []

    import time
    import requests

    # 缓存目录
    cache_dir = os.path.join(BASE_DIR, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"kline_{code}.json")

    # 检查缓存（15分钟内有效）
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
                cache_time = cached.get('timestamp', 0)
                if time.time() - cache_time < 900:  # 15分钟缓存
                    return cached.get('data', [])
        except:
            pass

    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 添加延迟避免请求过快
            if attempt > 0:
                time.sleep(2 ** attempt)  # 指数退避: 2s, 4s

            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
            if df is None or df.empty:
                print(f"⚠️  {code} 返回空数据，重试 {attempt+1}/{max_retries}")
                continue

            df = df.tail(days)
            result = []
            for _, row in df.iterrows():
                result.append({
                    "high":  float(row.get("最高", 0)),
                    "low":   float(row.get("最低", 0)),
                    "close": float(row.get("收盘", 0))
                })

            # 写入缓存
            try:
                with open(cache_file, 'w') as f:
                    json.dump({'timestamp': time.time(), 'data': result}, f)
            except:
                pass

            return result

        except requests.exceptions.ConnectionError as e:
            print(f"⚠️  {code} 连接失败 (尝试 {attempt+1}/{max_retries})")
            if attempt == max_retries - 1:
                break
        except Exception as e:
            print(f"⚠️  {code} 获取K线失败 (尝试 {attempt+1}/{max_retries}): {str(e)[:50]}")
            if attempt == max_retries - 1:
                break

    # 如果都失败了，尝试读取缓存（即使过期）
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
                print(f"ℹ️  {code} 使用缓存数据")
                return cached.get('data', [])
        except:
            pass

    return []

def calc_atr(klines, period=ATR_PERIOD):
    """计算 ATR，兼容浮点列表和字典列表两种格式"""
    import numpy as np
    if not klines or len(klines) < period + 1:
        return 0.0
    # 判断格式：纯浮点列表（data_manager返回）
    if isinstance(klines[0], (int, float)):
        prices = [float(x) for x in klines if x and float(x) > 0]
        if len(prices) < period + 1:
            return 0.0
        atr = np.mean(np.abs(np.diff(prices[-period-1:])))
        return round(float(atr), 4)
    # 字典列表格式（原akshare格式）
    if len(klines) < 2:
        return 0.0
    trs = []
    for i in range(1, len(klines)):
        h, l, pc = klines[i]["high"], klines[i]["low"], klines[i-1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    recent = trs[-period:] if len(trs) >= period else trs
    return sum(recent) / len(recent)

def calc_stop_loss(cost, current, atr):
    """计算止损价，取 ATR止损 和 硬性止损 中较高者"""
    atr_stop  = current - ATR_MULTIPLIER * atr if atr > 0 else None
    hard_stop = cost * (1 - MAX_LOSS_RATIO)
    stop_price = max(atr_stop, hard_stop) if atr_stop else hard_stop
    return {
        "atr_stop":      round(atr_stop, 3) if atr_stop else None,
        "hard_stop":     round(hard_stop, 3),
        "stop_price":    round(stop_price, 3),
        "loss_ratio_pct": round((stop_price - cost) / cost * 100, 2)
    }

def check_all_positions(send_alert=True):
    """检查所有持仓止损状态，返回触发止损的股票列表"""
    portfolio = load_portfolio()
    holdings = portfolio.get("positions", {})
    alerts = []

    print(f"\n{'='*50}")
    print(f"止损检查 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    for code, info in holdings.items():
        cost    = info.get("cost", 0)
        qty     = info.get("shares", 0)
        current = info.get("current_price", cost)

        if qty <= 0 or cost <= 0:
            continue

        klines = get_kline(code, days=30)
        atr    = calc_atr(klines) if klines else 0
        stop   = calc_stop_loss(cost, current, atr)
        triggered = current <= stop["stop_price"]
        float_pnl = (current - cost) * qty

        status = "🔴 触发止损" if triggered else "✅ 正常"
        print(f"\n股票: {code}")
        print(f"  成本: ¥{cost} | 现价: ¥{current} | 数量: {qty}股")
        print(f"  浮盈: ¥{float_pnl:.2f}")
        print(f"  ATR: {atr:.3f} | 止损价: ¥{stop['stop_price']} ({stop['loss_ratio_pct']}%) | {status}")

        if triggered:
            alerts.append({"code": code, "current": current,
                           "stop_price": stop["stop_price"],
                           "quantity": qty, "loss": float_pnl})
            blacklist_manager.add(code,
                reason=f"触发止损: 现价{current}≤止损价{stop['stop_price']}",
                days=5)

    if not alerts:
        print("\n✅ 所有持仓均未触发止损")
    else:
        print(f"\n⚠️  {len(alerts)} 只股票触发止损: {[a['code'] for a in alerts]}")

    return alerts

if __name__ == "__main__":
    print("=== ATR止损模块测试 ===")
    test_klines = [
        {"high": 15.0, "low": 14.0, "close": 14.5},
        {"high": 15.5, "low": 14.2, "close": 15.0},
        {"high": 15.8, "low": 14.8, "close": 15.3},
        {"high": 15.6, "low": 14.5, "close": 14.8},
        {"high": 14.9, "low": 14.0, "close": 14.3},
    ]
    atr = calc_atr(test_klines, period=4)
    print(f"测试ATR: {atr:.4f}")
    stop = calc_stop_loss(cost=15.2, current=14.68, atr=atr)
    print(f"601116 止损计算: {stop}")
    print("\n检查实际持仓:")
    check_all_positions()
