#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三源冗余数据管理器 v2.0
优先级: 腾讯直连 > MomaAPI > Baostock历史
"""
import baostock as bs
import pandas as pd
import time
import requests
from typing import Optional

# 尝试导入 MomaAPI
try:
    import sys
    sys.path.insert(0, '/Users/john.wu/quant_system')
    from data_fetcher import get_stock_realtime as moma_get_realtime
    from data_fetcher import get_stock_daily as moma_get_daily
    MOMA_AVAILABLE = True
except:
    MOMA_AVAILABLE = False


class RobustDataSourceManager:
    """
    三源冗余数据管理器 v2.0
    修复网络问题，优先使用可用的接口
    """
    
    def __init__(self):
        bs.login()
        self._cache = {}
        self._cache_time = {}
        self.CACHE_TTL = 25  # 实时数据缓存25秒（轮询60秒时保证每轮新数据）
    
    # ─────────────────────────────────────────
    # 实时行情：三路备份
    # ─────────────────────────────────────────
    def get_realtime_price(self, stock_code: str) -> Optional[dict]:
        """
        stock_code: '600519' 或 '000858'（不带市场后缀）
        返回: {'code': '600519', 'price': 1750.0, 'change_pct': 1.2, 'volume': 12345, 'source': 'tencent'}
        """
        # 检查缓存
        cache_key = f"rt_{stock_code}"
        if cache_key in self._cache:
            if time.time() - self._cache_time[cache_key] < self.CACHE_TTL:
                return self._cache[cache_key]
        
        # 方案1：腾讯直连（最稳定）
        result = self._try_tencent_direct(stock_code)
        if result and result.get('price', 0) > 0:
            self._cache[cache_key] = result
            self._cache_time[cache_key] = time.time()
            return result
        
        # 方案2：MomaAPI
        result = self._try_moma(stock_code)
        if result and result.get('price', 0) > 0:
            self._cache[cache_key] = result
            self._cache_time[cache_key] = time.time()
            return result
        
        # 方案3：Baostock 估算（收盘后）
        result = self._try_baostock_estimate(stock_code)
        if result:
            self._cache[cache_key] = result
            self._cache_time[cache_key] = time.time()
            return result
        
        print(f"⚠️ {stock_code} 三路数据源均失败")
        return None
    
    def _try_tencent_direct(self, code: str) -> Optional[dict]:
        """腾讯股票接口 - 直接HTTP，最稳定"""
        try:
            market = "sh" if code.startswith(("6", "5")) else "sz"
            url = f"http://qt.gtimg.cn/q={market}{code}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'Referer': 'https://finance.qq.com'
            }
            resp = requests.get(url, headers=headers, timeout=5)
            resp.encoding = 'gbk'
            
            data_str = resp.text
            if '~' not in data_str:
                return None
            
            parts = data_str.split('~')
            if len(parts) < 32:
                return None
            
            prev_close = float(parts[4]) if parts[4] else 0
            price = float(parts[3]) if parts[3] else 0
            change_pct = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0
            
            return {
                'code': code,
                'name': parts[1],
                'price': price,
                'change_pct': round(change_pct, 2),
                'volume': float(parts[6]) if parts[6] else 0,
                'amount': float(parts[37]) if len(parts) > 37 and parts[37] else 0,
                'high': float(parts[33]) if len(parts) > 33 and parts[33] else 0,
                'low': float(parts[34]) if len(parts) > 34 and parts[34] else 0,
                'open': float(parts[5]) if parts[5] else 0,
                'prev_close': prev_close,
                'source': 'tencent'
            }
        except Exception as e:
            # print(f"腾讯接口失败: {e}")
            return None
    
    def _try_moma(self, code: str) -> Optional[dict]:
        """MomaAPI"""
        if not MOMA_AVAILABLE:
            return None
        try:
            data = moma_get_realtime(code)
            if data and 'price' in data:
                return {
                    'code': code,
                    'price': data.get('price', 0),
                    'change_pct': data.get('change_pct', 0),
                    'volume': data.get('volume', 0),
                    'open': data.get('open', 0),
                    'high': data.get('high', 0),
                    'low': data.get('low', 0),
                    'prev_close': data.get('prev_close', 0),
                    'source': 'moma'
                }
        except:
            pass
        return None
    
    def _try_baostock_estimate(self, code: str) -> Optional[dict]:
        """Baostock 估算（用昨日收盘价）"""
        try:
            market = "sh" if code.startswith(("6", "5")) else "sz"
            rs = bs.query_history_k_data_plus(
                f"{market}.{code}",
                "date,close",
                start_date=(pd.Timestamp.now() - pd.Timedelta(days=5)).strftime('%Y-%m-%d'),
                end_date=pd.Timestamp.now().strftime('%Y-%m-%d'),
                frequency="d",
                adjustflag="3"
            )
            rows = []
            while rs.error_code == '0' and rs.next():
                rows.append(rs.get_row_data())
            if rows:
                last = rows[-1]
                return {
                    'code': code,
                    'price': float(last[1]) if len(last) > 1 else 0,
                    'change_pct': 0,
                    'volume': 0,
                    'source': 'baostock_est'
                }
        except:
            pass
        return None
    
    # ─────────────────────────────────────────
    # 批量获取实时行情
    # ─────────────────────────────────────────
    def get_realtime_prices(self, stock_codes: list) -> dict:
        """批量获取实时行情"""
        results = {}
        for code in stock_codes:
            result = self.get_realtime_price(code)
            if result:
                results[code] = result
        return results
    
    # ─────────────────────────────────────────
    # 历史日线：Baostock
    # ─────────────────────────────────────────
    def get_history_kline(self, code: str, days: int = 60) -> pd.DataFrame:
        """获取历史日K线，用于因子计算"""
        try:
            end = pd.Timestamp.now().strftime('%Y-%m-%d')
            start = (pd.Timestamp.now() - pd.Timedelta(days=days*2)).strftime('%Y-%m-%d')
            
            market = "sh" if code.startswith(("6", "5")) else "sz"
            rs = bs.query_history_k_data_plus(
                f"{market}.{code}",
                "date,open,high,low,close,volume,amount,turn,pctChg",
                start_date=start,
                end_date=end,
                frequency="d",
                adjustflag="3"
            )
            
            rows = []
            while rs.error_code == '0' and rs.next():
                rows.append(rs.get_row_data())
            
            df = pd.DataFrame(rows, columns=rs.fields)
            df = df.replace('', None).dropna(subset=['close'])
            
            for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').tail(days).reset_index(drop=True)
            return df
        
        except Exception as e:
            print(f"Baostock 历史数据失败: {e}")
            return pd.DataFrame()
    
    # ─────────────────────────────────────────
    # 因子计算
    # ─────────────────────────────────────────
    def calculate_ma(self, df: pd.DataFrame, periods: list = [5, 10, 20]) -> pd.DataFrame:
        """计算移动平均线"""
        for p in periods:
            df[f'ma{p}'] = df['close'].rolling(p).mean()
        return df
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """计算RSI"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        df[f'rsi{period}'] = 100 - (100 / (1 + rs))
        return df
    
    def calculate_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算MACD"""
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['histogram'] = df['macd'] - df['signal']
        return df
    
    def __del__(self):
        try:
            bs.logout()
        except:
            pass


if __name__ == "__main__":
    dm = RobustDataSourceManager()
    
    test_codes = ['600519', '000001', '601318', '002737']
    
    print("=== 测试实时行情 ===")
    for code in test_codes:
        result = dm.get_realtime_price(code)
        if result:
            print(f"✓ {code}: ¥{result['price']:.2f} ({result['change_pct']:+.2f}%) [{result['source']}]")
        else:
            print(f"✗ {code}: 获取失败")
    
    print("\n=== 测试历史K线 + 因子 ===")
    df = dm.get_history_kline('600519', 30)
    if not df.empty:
        df = dm.calculate_ma(df)
        df = dm.calculate_rsi(df)
        df = dm.calculate_macd(df)
        print(f"✓ 600519: {len(df)} 条K线 + MA5/MA20/RSI/MACD")
        print(df[['date', 'close', 'ma5', 'ma20', 'rsi14', 'macd']].tail(5))
