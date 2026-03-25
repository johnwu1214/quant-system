import json
import os
import time
import logging
import numpy as np
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

BASE_DIR = "/root/quant-system"
KLINE_CACHE_FILE = os.path.join(BASE_DIR, "kline_cache.json")
QLIB_DATA_DIR = "/root/qlib_data/cn_data_community"
CALENDAR_FILE = os.path.join(QLIB_DATA_DIR, "calendars/day.txt")
PRICE_CACHE = {}
PRICE_CACHE_TIME = {}

# ============================================================
# 内部工具：读取Qlib二进制文件
# ============================================================
def _read_qlib_bin(filepath):
    try:
        with open(filepath, 'rb') as f:
            return np.frombuffer(f.read(), dtype='<f4')
    except Exception as e:
        logger.debug("读取bin文件失败 %s: %s", filepath, e)
        return np.array([])

def _load_calendar():
    try:
        with open(CALENDAR_FILE) as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logger.warning("读取日历失败: %s", e)
        return []

def _get_qlib_closes(code, days=60):
    """
    直读cn_data_community二进制文件获取收盘价序列。
    返回最近days条，数值为相对价格（可直接用于RSI/MACD/MA计算）。
    """
    exchange = "sh" if code.startswith("6") else "sz"
    bin_path = os.path.join(QLIB_DATA_DIR, "features",
                            exchange + code, "close.day.bin")
    factor_path = os.path.join(QLIB_DATA_DIR, "features",
                               exchange + code, "factor.day.bin")
    if not os.path.exists(bin_path):
        logger.warning("Qlib数据文件不存在: %s", bin_path)
        return []

    calendar = _load_calendar()
    raw = _read_qlib_bin(bin_path)
    if len(raw) == 0:
        return []

    # 用复权因子还原真实价格
    if os.path.exists(factor_path):
        factor = _read_qlib_bin(factor_path)
        n = min(len(raw), len(factor))
        prices = np.where(factor[:n] != 0, raw[:n] / np.where(factor[:n] != 0, factor[:n], 1), np.nan).astype(float)
    else:
        prices = raw.astype(float)

    # 过滤无效值
    prices = np.where((prices > 0) & (prices < 10000), prices, np.nan)
    valid = prices[~np.isnan(prices)]

    if len(valid) < 20:
        return []

    result = [round(float(v), 3) for v in valid[-days:]]
    logger.debug("Qlib直读成功 %s: %d条 最新=%.2f", code, len(result), result[-1])
    return result

# ============================================================
# Layer 2: 实时价格（新浪主力 + 腾讯备用）
# ============================================================
def get_realtime_price(code, max_age_seconds=55):
    now = time.time()
    if code in PRICE_CACHE and (now - PRICE_CACHE_TIME.get(code, 0)) < max_age_seconds:
        return PRICE_CACHE[code]
    result = _fetch_sina_price(code) or _fetch_tencent_price(code)
    if result:
        PRICE_CACHE[code] = result
        PRICE_CACHE_TIME[code] = now
    return result

def _fetch_sina_price(code):
    try:
        prefix = "sh" if code.startswith("6") else "sz"
        url = "https://hq.sinajs.cn/list=" + prefix + code
        r = requests.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=5)
        parts = r.text.split('"')[1].split(',')
        if len(parts) > 3 and parts[3] and float(parts[3]) > 0:
            price = float(parts[3])
            yclose = float(parts[2]) if parts[2] else price
            pct = round((price / yclose - 1) * 100, 2) if yclose else 0
            return {"price": price, "pct_chg": pct, "source": "sina"}
    except Exception as e:
        logger.debug("sina fail %s: %s", code, e)
    return None

def _fetch_tencent_price(code):
    try:
        prefix = "sh" if code.startswith("6") else "sz"
        url = "https://qt.gtimg.cn/q=" + prefix + code
        r = requests.get(url, timeout=5)
        parts = r.text.split('~')
        if len(parts) > 32 and parts[3] and float(parts[3]) > 0:
            price = float(parts[3])
            pct = float(parts[32]) if parts[32] else 0
            return {"price": price, "pct_chg": pct, "source": "tencent"}
    except Exception as e:
        logger.debug("tencent fail %s: %s", code, e)
    return None

# ============================================================
# Layer 1: K线缓存（JSON文件，每日更新一次）
# ============================================================
def _load_kline_cache():
    today = datetime.now().strftime("%Y%m%d")
    try:
        if os.path.exists(KLINE_CACHE_FILE):
            with open(KLINE_CACHE_FILE) as f:
                data = json.load(f)
            if data.get("date") == today:
                return data.get("klines", {})
    except Exception as e:
        logger.warning("读取K线缓存失败: %s", e)
    return {}

def _save_kline_cache(klines_dict):
    today = datetime.now().strftime("%Y%m%d")
    try:
        with open(KLINE_CACHE_FILE, "w") as f:
            json.dump({"date": today, "klines": klines_dict,
                       "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, f)
        logger.info("K线缓存已保存: %d只", len(klines_dict))
    except Exception as e:
        logger.error("保存K线缓存失败: %s", e)

def get_history_kline(code, days=60):
    """
    获取历史K线。优先级：
    1. 今日JSON缓存（交易时段内命中则直接返回，零网络请求）
    2. Qlib二进制直读（本地文件，无网络，毫秒级）
    3. 东财HTTP接口（仅开盘前批量更新时使用）
    """
    # 1. JSON缓存
    cache = _load_kline_cache()
    if code in cache and len(cache[code]) >= 20:
        data = cache[code]
        return data[-days:] if len(data) > days else data

    # 2. Qlib直读（本地，零网络）
    closes = _get_qlib_closes(code, days)
    if closes and len(closes) >= 20:
        cache[code] = closes
        _save_kline_cache(cache)
        logger.info("K线来源: Qlib本地 %s %d条", code, len(closes))
        return closes

    # 3. 东财接口（最后尝试）
    closes = _fetch_kline_eastmoney(code, days)
    if closes and len(closes) >= 20:
        cache[code] = closes
        _save_kline_cache(cache)
        logger.info("K线来源: 东财接口 %s %d条", code, len(closes))
        return closes

    logger.warning("K线全部来源失败 %s", code)
    return []

def _fetch_kline_eastmoney(code, days=60):
    try:
        mkt = "1" if code.startswith("6") else "0"
        edate = datetime.now().strftime("%Y%m%d")
        sdate = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
        url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get"
               "?secid=" + mkt + "." + code
               + "&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56,f57"
               + "&klt=101&fqt=1&beg=" + sdate + "&end=" + edate
               + "&lmt=" + str(days))
        r = requests.get(url, timeout=8)
        kdata = r.json().get("data", {})
        if kdata and kdata.get("klines"):
            closes = [float(k.split(',')[2]) for k in kdata["klines"]]
            if len(closes) >= 20:
                return closes
    except Exception as e:
        logger.debug("eastmoney kline fail %s: %s", code, e)
    return []

# ============================================================
# 开盘前批量预热（09:15 crontab调用）
# ============================================================
def update_kline_cache(codes, days=60):
    """
    批量预热K线缓存。优先Qlib直读（无速率限制），东财作为补充。
    """
    cache = {}
    success = 0
    qlib_count = 0
    net_count = 0
    logger.info("开始批量更新K线缓存，共 %d 只", len(codes))

    for i, code in enumerate(codes):
        # 优先Qlib本地（无网络，无速率限制）
        closes = _get_qlib_closes(code, days)
        if closes and len(closes) >= 20:
            cache[code] = closes
            success += 1
            qlib_count += 1
            continue

        # Qlib失败则用东财（控制速率）
        time.sleep(0.5)
        closes = _fetch_kline_eastmoney(code, days)
        if closes and len(closes) >= 20:
            cache[code] = closes
            success += 1
            net_count += 1
        else:
            logger.warning("K线更新失败 %s", code)

        if (i + 1) % 5 == 0:
            time.sleep(1.0)

    _save_kline_cache(cache)
    rate = success / len(codes) * 100 if codes else 0
    logger.info("K线缓存更新完成: %d/%d (%.0f%%) Qlib=%d 东财=%d",
                success, len(codes), rate, qlib_count, net_count)
    if rate < 50:
        logger.warning("K线更新成功率低于50%%，信号质量受损！")
    return success, len(codes)

def health_check(codes):
    codes = _clean_codes(codes)
    report = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "realtime_ok": False,
        "kline_cache_ok": False,
        "kline_coverage": 0.0,
        "qlib_ok": False,
        "issues": []
    }
    # 实时接口
    test_code = codes[0] if codes else "601116"
    price_data = get_realtime_price(test_code)
    if price_data and price_data.get("price", 0) > 0:
        report["realtime_ok"] = True
    else:
        report["issues"].append("实时价格接口异常: " + test_code)

    # Qlib本地数据
    test_closes = _get_qlib_closes(test_code, 60)
    if test_closes and len(test_closes) >= 20:
        report["qlib_ok"] = True
    else:
        report["issues"].append("Qlib本地数据异常: " + test_code)

    # K线缓存覆盖率
    cache = _load_kline_cache()
    covered = sum(1 for c in codes if c in cache and len(cache[c]) >= 20)
    report["kline_coverage"] = covered / len(codes) if codes else 0
    report["kline_cache_ok"] = report["kline_coverage"] >= 0.8
    if not report["kline_cache_ok"]:
        report["issues"].append(
            "K线缓存覆盖率仅 %.0f%% (需>=80%%)" % (report["kline_coverage"] * 100))
    return report

def _clean_codes(codes):
    """过滤出合法的A股代码（6位纯数字）"""
    import re
    return [c for c in codes if c and re.match(r'^\d{6}$', str(c))]

# ══════════════════════════════════════════
# 单股熔断机制：连续失败3次后当日不再重试
# ══════════════════════════════════════════
_CIRCUIT_BREAKER = {}   # {code: {"fails": 0, "broken_at": "2026-03-19"}}

def _is_broken(code):
    """检查该股今日是否已熔断"""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    cb = _CIRCUIT_BREAKER.get(code, {})
    return cb.get("broken_at") == today and cb.get("fails", 0) >= 3

def _record_fail(code):
    """记录一次失败，达到3次触发熔断"""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    cb = _CIRCUIT_BREAKER.get(code, {"fails": 0, "broken_at": today})
    if cb.get("broken_at") != today:
        cb = {"fails": 0, "broken_at": today}
    cb["fails"] += 1
    _CIRCUIT_BREAKER[code] = cb
    if cb["fails"] == 3:
        logger.warning(f"[熔断] {code} 今日连续失败3次，切换全缓存模式")

def _reset_fail(code):
    """成功后清零失败计数"""
    _CIRCUIT_BREAKER.pop(code, None)
