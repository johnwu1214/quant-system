#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能多源数据调度模块 v2.0
优先级：mootdx（盘中实时）> BaoStock（收盘后主力）> AkShare（备用）
作者：quant-system
更新：2026-03-25
"""

import os
import json
import time
import warnings
import logging
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.WARNING)
log = logging.getLogger('data_source')

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / 'config.json'

# ── 时段判断 ──────────────────────────────────────────────
def is_trading_hours() -> bool:
    """是否在交易时段 09:25~15:05"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 100 + now.minute
    return 925 <= t <= 1505

def is_after_close() -> bool:
    """是否收盘后 15:05 以后"""
    now = datetime.now()
    t = now.hour * 100 + now.minute
    return t >= 1505

# ── mootdx：盘中实时主力 ──────────────────────────────────
_mootdx_client = None

def _get_mootdx():
    global _mootdx_client
    if _mootdx_client is None:
        try:
            from mootdx.quotes import Quotes
            _mootdx_client = Quotes.factory(market='std', bestip=False, timeout=15)
        except Exception as e:
            log.warning(f'mootdx 初始化失败: {e}')
    return _mootdx_client

def get_realtime_price_mootdx(symbol: str) -> dict | None:
    """
    获取单只股票实时报价
    返回: {'symbol': '300502', 'price': 471.8, 'open': 490.21,
           'high': 492.0, 'low': 463.0, 'last_close': 468.0,
           'volume': 345932, 'source': 'mootdx'}
    """
    try:
        client = _get_mootdx()
        if client is None:
            return None
        df = client.quotes(symbol=symbol)
        if df is None or len(df) == 0:
            return None
        row = df.iloc[0]
        return {
            'symbol':     symbol,
            'price':      float(row.get('price', 0)),
            'open':       float(row.get('open', 0)),
            'high':       float(row.get('high', 0)),
            'low':        float(row.get('low', 0)),
            'last_close': float(row.get('last_close', 0)),
            'volume':     int(row.get('volume', 0)),
            'source':     'mootdx'
        }
    except Exception as e:
        log.warning(f'mootdx 实时报价失败 {symbol}: {e}')
        return None

def get_daily_mootdx(symbol: str, days: int = 60) -> 'pd.DataFrame | None':
    """获取最近 N 天日线（mootdx，盘中可用）"""
    try:
        client = _get_mootdx()
        if client is None:
            return None
        df = client.bars(symbol=symbol, frequency=9, offset=days)
        if df is None or len(df) == 0:
            return None
        import pandas as pd
        df = df[['open', 'close', 'high', 'low', 'vol', 'amount']].copy()
        df.columns = ['open', 'close', 'high', 'low', 'volume', 'amount']
        df.index = pd.to_datetime(df.index.astype(str).str[:10])
        df.index.name = 'date'
        return df.sort_index()
    except Exception as e:
        log.warning(f'mootdx 日线失败 {symbol}: {e}')
        return None

# ── BaoStock：收盘后主力 ──────────────────────────────────
_bs_logged_in = False

def _bs_login():
    global _bs_logged_in
    if not _bs_logged_in:
        try:
            import baostock as bs
            bs.login()
            _bs_logged_in = True
        except Exception as e:
            log.warning(f'BaoStock 登录失败: {e}')

def _bs_code(symbol: str) -> str:
    """300502 → sz.300502, 600036 → sh.600036"""
    if symbol.startswith('6'):
        return f'sh.{symbol}'
    return f'sz.{symbol}'

def get_daily_baostock(symbol: str, start_date: str, end_date: str) -> 'pd.DataFrame | None':
    """
    获取日线数据（BaoStock）
    start_date / end_date 格式：'2026-03-01'
    """
    try:
        import baostock as bs
        import pandas as pd
        _bs_login()
        code = _bs_code(symbol)
        rs = bs.query_history_k_data_plus(
            code,
            'date,open,high,low,close,volume,amount,turn,pctChg',
            start_date=start_date,
            end_date=end_date,
            frequency='d',
            adjustflag='3'   # 不复权，与实盘一致
        )
        rows = []
        while rs.error_code == '0' and rs.next():
            rows.append(rs.get_row_data())
        if not rows:
            return None
        df = pd.DataFrame(rows, columns=rs.fields)
        df = df[df['open'] != ''].copy()
        for col in ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.set_index('date', inplace=True)
        df.index = pd.to_datetime(df.index)
        return df.sort_index()
    except Exception as e:
        log.warning(f'BaoStock 日线失败 {symbol}: {e}')
        return None

def get_csi300_members_baostock() -> list:
    """获取沪深300当前成分股列表"""
    try:
        import baostock as bs
        _bs_login()
        rs = bs.query_hs300_stocks()
        stocks = []
        while rs.error_code == '0' and rs.next():
            row = rs.get_row_data()
            # row = [updateDate, code, code_name]
            code = row[1].split('.')[1] if '.' in row[1] else row[1]
            stocks.append({'code': code, 'name': row[2]})
        return stocks
    except Exception as e:
        log.warning(f'BaoStock 成分股失败: {e}')
        return []

# ── AkShare：备用 ─────────────────────────────────────────
def get_daily_akshare(symbol: str, start_date: str, end_date: str) -> 'pd.DataFrame | None':
    """AkShare 日线（收盘后稳定，盘中可能限速）"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period='daily',
            start_date=start_date.replace('-', ''),
            end_date=end_date.replace('-', ''),
            adjust='qfq'
        )
        if df is None or len(df) == 0:
            return None
        df = df.rename(columns={
            '日期': 'date', '开盘': 'open', '最高': 'high',
            '最低': 'low', '收盘': 'close', '成交量': 'volume',
            '成交额': 'amount', '涨跌幅': 'pctChg'
        })
        df.set_index('date', inplace=True)
        import pandas as pd
        df.index = pd.to_datetime(df.index)
        return df.sort_index()
    except Exception as e:
        log.warning(f'AkShare 日线失败 {symbol}: {e}')
        return None

# ── 统一对外接口 ──────────────────────────────────────────
def get_price(symbol: str) -> float:
    """
    获取最新价格，智能选源：
    盘中 → mootdx → AkShare实时 → BaoStock昨收
    盘后 → BaoStock/AkShare
    """
    # 盘中优先 mootdx
    if is_trading_hours():
        r = get_realtime_price_mootdx(symbol)
        if r and r['price'] > 0:
            return r['price']

    # 收盘后用 BaoStock 昨日收盘
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        df = get_daily_baostock(symbol, week_ago, today)
        if df is not None and len(df) > 0:
            return float(df['close'].iloc[-1])
    except Exception:
        pass

    # 最后备用 mootdx 最新日线
    df = get_daily_mootdx(symbol, days=5)
    if df is not None and len(df) > 0:
        return float(df['close'].iloc[-1])

    return 0.0

def get_daily(symbol: str, start_date: str, end_date: str) -> 'pd.DataFrame | None':
    """
    获取日线数据，智能选源：
    盘中 → mootdx（最新）→ BaoStock（历史）
    盘后 → BaoStock（主力）→ AkShare（备用）→ mootdx
    """
    if is_trading_hours():
        # 盘中：mootdx 获取最近数据，BaoStock 补历史
        df_td = get_daily_mootdx(symbol, days=60)
        df_bs = get_daily_baostock(symbol, start_date, end_date)
        if df_td is not None and df_bs is not None:
            import pandas as pd
            df = pd.concat([df_bs, df_td[~df_td.index.isin(df_bs.index)]])
            return df.sort_index()
        return df_bs or df_td

    # 收盘后：BaoStock 主力
    df = get_daily_baostock(symbol, start_date, end_date)
    if df is not None and len(df) >= 5:
        return df

    # 备用 AkShare
    df = get_daily_akshare(symbol, start_date, end_date)
    if df is not None and len(df) >= 5:
        return df

    # 最后 mootdx
    return get_daily_mootdx(symbol, days=120)

def get_csi300_members() -> list:
    """获取沪深300成分股，BaoStock 主力"""
    stocks = get_csi300_members_baostock()
    if stocks:
        return stocks
    # 备用 AkShare
    try:
        import akshare as ak
        df = ak.index_stock_cons_weight_csindex(symbol='000300')
        return [{'code': str(r['成分券代码']).zfill(6), 'name': r['成分券名称']}
                for _, r in df.iterrows()]
    except Exception:
        return []

def get_batch_prices(symbols: list) -> dict:
    """
    批量获取实时价格（盘中用 mootdx 逐个查，盘后用 BaoStock）
    返回: {'300502': 471.8, '600089': 29.0, ...}
    """
    result = {}
    if is_trading_hours():
        for sym in symbols:
            r = get_realtime_price_mootdx(sym)
            if r and r['price'] > 0:
                result[sym] = r['price']
            time.sleep(0.05)   # 50ms 间隔，不超频
    else:
        today = datetime.now().strftime('%Y-%m-%d')
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        for sym in symbols:
            df = get_daily_baostock(sym, week_ago, today)
            if df is not None and len(df) > 0:
                result[sym] = float(df['close'].iloc[-1])
            time.sleep(0.1)
    return result

# ── 自检 ──────────────────────────────────────────────────
if __name__ == '__main__':
    print('=' * 50)
    print(f'智能数据源 v2.0 自检  {datetime.now().strftime("%H:%M:%S")}')
    print(f'当前时段: {"盘中" if is_trading_hours() else "盘后"}')
    print('=' * 50)

    # 1. mootdx 实时
    print('\n[1] mootdx 实时报价')
    r = get_realtime_price_mootdx('300502')
    if r:
        print(f'  ✅ 300502 现价={r["price"]}  高={r["high"]}  低={r["low"]}')
    else:
        print('  ❌ 失败')

    # 2. mootdx 日线
    print('\n[2] mootdx 日线（最近5天）')
    df = get_daily_mootdx('300502', days=5)
    if df is not None:
        print(f'  ✅ {len(df)} 条\n{df[["open","close","volume"]].tail(3).to_string()}')
    else:
        print('  ❌ 失败')

    # 3. BaoStock 日线
    print('\n[3] BaoStock 日线')
    df = get_daily_baostock('300502', '2026-03-18', '2026-03-25')
    if df is not None:
        print(f'  ✅ {len(df)} 条\n{df[["open","close","volume"]].tail(3).to_string()}')
    else:
        print('  ❌ 失败')

    # 4. 成分股
    print('\n[4] 沪深300成分股')
    members = get_csi300_members()
    print(f'  ✅ {len(members)} 只  示例: {members[:3]}' if members else '  ❌ 失败')

    # 5. 批量报价（持仓）
    print('\n[5] 批量实时报价（持仓3只）')
    prices = get_batch_prices(['300394', '600089', '300502'])
    for sym, p in prices.items():
        print(f'  ✅ {sym}: ¥{p}')

    print('\n✅ 自检完成')
