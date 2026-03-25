#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据获取模块 - MomaAPI + Tushare
"""
import requests
import pandas as pd
from datetime import datetime, timedelta
import os
import numpy as np

DATA_DIR = os.path.expanduser("~/quant_system/data")

# ==================== MomaAPI ====================
MOMA_TOKEN = "6C2D188A-7482-419D-905E-D146DA9964F0"
MOMA_BASE = "http://api.momaapi.com"

def format_stock_code(code: str) -> tuple:
    """格式化股票代码为 (code, market)"""
    code = code.strip()
    if code.startswith('6'):
        return code, 'SH'
    elif code.startswith(('0', '3')):
        return code, 'SZ'
    else:
        return code, 'SZ'

def get_realtime_moma(stock_code: str) -> dict:
    """获取实时行情 - MomaAPI"""
    try:
        url = f"{MOMA_BASE}/hsstock/real/time/{stock_code}/{MOMA_TOKEN}"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        
        return {
            'code': stock_code,
            'price': data.get('p', 0),
            'open': data.get('o', 0),
            'high': data.get('h', 0),
            'low': data.get('l', 0),
            'prev_close': data.get('yc', 0),
            'change_pct': data.get('pc', 0) * 100,
            'volume': data.get('v', 0),
            'amount': data.get('cje', 0),
            'time': data.get('t', '')
        }
    except Exception as e:
        print(f"MomaAPI实时行情失败: {e}")
        return {}

def get_daily_moma(stock_code: str, days: int = 30) -> pd.DataFrame:
    """获取日线数据 - MomaAPI"""
    try:
        code, market = format_stock_code(stock_code)
        url = f"{MOMA_BASE}/hsstock/latest/{code}.{market}/d/n/{MOMA_TOKEN}?lt={days}"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df = df.rename(columns={
            't': 'date',
            'o': 'open', 
            'h': 'high',
            'l': 'low',
            'c': 'close',
            'v': 'volume'
        })
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        return df[['date', 'open', 'high', 'low', 'close', 'volume']]
        
    except Exception as e:
        print(f"MomaAPI日线失败: {e}")
        return pd.DataFrame()

def get_macd_moma(stock_code: str, days: int = 30) -> pd.DataFrame:
    """获取MACD指标 - MomaAPI"""
    try:
        code, market = format_stock_code(stock_code)
        url = f"{MOMA_BASE}/hsstock/history/macd/{code}.{market}/d/n/{MOMA_TOKEN}?lt={days}"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df = df.rename(columns={'t': 'date'})
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        return df
        
    except Exception as e:
        print(f"MomaAPI MACD失败: {e}")
        return pd.DataFrame()


# ==================== Tushare 备用 ====================
TUSHARE_TOKEN = "8c0e6500f7ed08a0538cc750abafd70b444ea5e8674a74fd2b2b0dc4"

def get_daily_tushare(stock_code: str, days: int = 100) -> pd.DataFrame:
    """获取日线数据 - Tushare备用"""
    try:
        import tushare as ts
        pro = ts.pro_api(TUSHARE_TOKEN)
        
        # 格式化代码
        if '.' not in stock_code:
            if stock_code.startswith('6'):
                stock_code = f"{stock_code}.SH"
            else:
                stock_code = f"{stock_code}.SZ"
        
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days+30)).strftime('%Y%m%d')
        
        df = pro.daily(ts_code=stock_code, start_date=start_date, end_date=end_date)
        
        if df.empty:
            return pd.DataFrame()
        
        df = df.rename(columns={'trade_date': 'date', 'vol': 'volume'})
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        return df[['date', 'open', 'high', 'low', 'close', 'volume']].tail(days)
        
    except Exception as e:
        print(f"Tushare失败: {e}")
        return pd.DataFrame()


# ==================== 统一接口 ====================

def get_stock_daily(stock_code: str, days: int = 30) -> pd.DataFrame:
    """获取日线数据（优先MomaAPI，备用Tushare）"""
    # 尝试 MomaAPI
    df = get_daily_moma(stock_code, days)
    if not df.empty:
        return df
    
    # 备用 Tushare
    df = get_daily_tushare(stock_code, days)
    if not df.empty:
        return df
    
    # 都失败则用模拟数据
    print("使用模拟数据")
    return get_mock_data(stock_code, days)


def get_stock_realtime(stock_code: str) -> dict:
    """获取实时行情"""
    data = get_realtime_moma(stock_code)
    if data:
        return data
    return get_realtime_tushare(stock_code)


def get_realtime_tushare(stock_code: str) -> dict:
    """Tushare实时（通过最新日线）"""
    try:
        df = get_daily_tushare(stock_code, 1)
        if not df.empty:
            latest = df.iloc[-1]
            return {
                'code': stock_code,
                'price': float(latest['close']),
                'volume': float(latest['volume'])
            }
    except:
        pass
    return {}


def get_mock_data(stock_code: str, days: int = 250) -> pd.DataFrame:
    """模拟数据（完全备用）"""
    np.random.seed(hash(stock_code) % 10000)
    end_date = datetime.now()
    dates = pd.date_range(end=end_date, periods=days, freq='B')
    initial_price = 10 + np.random.random() * 90
    returns = np.random.normal(0.001, 0.02, days)
    prices = initial_price * np.exp(np.cumsum(returns))
    
    return pd.DataFrame({
        'date': dates,
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, days)),
        'high': prices * (1 + np.random.uniform(0, 0.03, days)),
        'low': prices * (1 + np.random.uniform(-0.03, 0, days)),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, days)
    })


def save_data(df: pd.DataFrame, filename: str):
    """保存到本地"""
    if not df.empty:
        os.makedirs(DATA_DIR, exist_ok=True)
        path = os.path.join(DATA_DIR, f"{filename}.csv")
        df.to_csv(path, index=False)


# ==================== 测试 ====================
if __name__ == "__main__":
    print("=== 测试 MomaAPI ===")
    
    # 实时行情
    rt = get_realtime_moma("000001")
    print(f"实时: {rt.get('price')}元, 涨跌:{rt.get('change_pct', 0):.2f}%")
    
    # 日线
    df = get_daily_moma("000001", 5)
    print(f"日线: {len(df)}条")
    print(df)
    
    # MACD
    macd = get_macd_moma("000001", 5)
    print(f"MACD: {len(macd)}条")
    print(macd)
