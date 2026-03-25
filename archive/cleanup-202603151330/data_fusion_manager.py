#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源数据融合管理器
解决AkShare单点依赖问题
"""
import os
import sys
from typing import Optional, List
import pandas as pd

# 尝试导入各数据源
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except:
    AKSHARE_AVAILABLE = False

try:
    import efinance as ef
    EFINANCE_AVAILABLE = True
except:
    EFINANCE_AVAILABLE = False

try:
    import baostock as bs
    BAOSTOCK_AVAILABLE = True
except:
    BAOSTOCK_AVAILABLE = False

try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except:
    TUSHARE_AVAILABLE = False


class DataFusionManager:
    """多源数据融合管理器"""
    
    def __init__(self, tushare_token: str = None):
        self.tushare_token = tushare_token or os.environ.get("TUSHARE_TOKEN", "")
        
        # 初始化数据源
        self.sources = {
            'akshare': AKSHARE_AVAILABLE,
            'efinance': EFINANCE_AVAILABLE,
            'baostock': BAOSTOCK_AVAILABLE,
            'tushare': False
        }
        
        # 优先级的配置
        self.priority = ['baostock', 'akshare']  # baostock最稳定
        
        # 初始化Tushare
        if self.tushare_token and TUSHARE_AVAILABLE:
            try:
                self.ts_pro = ts.pro_api(self.tushare_token)
                self.sources['tushare'] = True
                print("✅ Tushare 已连接")
            except Exception as e:
                print(f"⚠️ Tushare 连接失败: {e}")
        
        # 初始化Baostock
        if BAOSTOCK_AVAILABLE:
            try:
                bs.login()
                print("✅ Baostock 已连接")
            except:
                pass
        
        # 打印可用数据源
        available = [k for k, v in self.sources.items() if v]
        print(f"📡 可用数据源: {', '.join(available)}")
    
    def get_stock_daily(self, code: str, days: int = 30) -> pd.DataFrame:
        """获取股票日线数据（多源融合）"""
        
        # 尝试各数据源
        for source in self.priority:
            try:
                if source == 'tushare' and self.sources['tushare']:
                    df = self._get_tushare_daily(code, days)
                elif source == 'efinance' and self.sources['efinance']:
                    df = self._get_efinance_daily(code, days)
                elif source == 'baostock' and self.sources['baostock']:
                    df = self._get_baostock_daily(code, days)
                elif source == 'akshare' and self.sources['akshare']:
                    df = self._get_akshare_daily(code, days)
                
                if df is not None and not df.empty:
                    print(f"✅ {code}: 从 {source} 获取 {len(df)} 条数据")
                    return df
                    
            except Exception as e:
                print(f"⚠️ {source} 获取 {code} 失败: {str(e)[:50]}")
                continue
        
        print(f"❌ 所有数据源均失败: {code}")
        return pd.DataFrame()
    
    def _get_tushare_daily(self, code: str, days: int) -> pd.DataFrame:
        """从Tushare获取"""
        ts_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
        
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days+30)).strftime('%Y%m%d')
        
        df = self.ts_pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        
        if df is not None:
            df = df.sort_values('trade_date')
            df = df.tail(days)
            # 标准化列名
            df = df.rename(columns={
                'trade_date': 'date',
                'vol': 'volume'
            })
        
        return df
    
    def _get_efinance_daily(self, code: str, days: int) -> pd.DataFrame:
        """从efinance获取"""
        df = ef.stock.get_quote_history(code, beg='20200101')
        
        if df is not None:
            df = df.tail(days)
            # 标准化
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume'
            })
        
        return df
    
    def _get_baostock_daily(self, code: str, days: int) -> pd.DataFrame:
        """从Baostock获取"""
        from datetime import datetime, timedelta
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days+30)).strftime('%Y-%m-%d')
        
        bs_code = f"sh.{code}" if code.startswith('6') else f"sz.{code}"
        
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2"
        )
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        if data_list:
            df = pd.DataFrame(data_list, columns=rs.fields)
            df = df.tail(days)
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        
        return df if data_list else pd.DataFrame()
    
    def _get_akshare_daily(self, code: str, days: int) -> pd.DataFrame:
        """从AkShare获取"""
        from datetime import datetime, timedelta
        
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=(datetime.now() - timedelta(days=days+30)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d"),
            adjust="qfq"
        )
        
        if df is not None:
            df = df.tail(days)
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume'
            })
        
        return df
    
    def get_realtime(self, code: str) -> dict:
        """获取实时行情"""
        
        # 优先用efinance（实时性好）
        if self.sources.get('efinance'):
            try:
                df = ef.stock.get_quote_belong(code)
                if df is not None and len(df) > 0:
                    # 取最新价
                    row = df.iloc[-1]
                    return {
                        'code': code,
                        'price': float(row.get('最新价', 0)),
                        'change_pct': float(row.get('涨跌幅', 0)),
                        'volume': float(row.get('成交量', 0))
                    }
            except:
                pass
        
        # 备用：直接返回None，让调用方处理
        return None
    
    def get_index_daily(self, index_code: str = "000300", days: int = 30) -> pd.DataFrame:
        """获取指数数据"""
        
        if self.sources.get('akshare'):
            try:
                symbol = f"sh{index_code}"
                df = ak.stock_zh_index_daily(symbol=symbol)
                if df is not None:
                    return df.tail(days)
            except:
                pass
        
        return pd.DataFrame()
    
    def close(self):
        """关闭连接"""
        if BAOSTOCK_AVAILABLE:
            try:
                bs.logout()
            except:
                pass


# 测试
if __name__ == "__main__":
    print("🧪 测试多源数据融合...")
    
    manager = DataFusionManager()
    
    # 测试获取日线
    print("\n📈 获取日线数据:")
    df = manager.get_stock_daily('600519', 5)
    if not df.empty:
        print(f"   成功: {len(df)} 条")
        print(df.tail(2))
    
    # 测试指数
    print("\n📊 获取指数数据:")
    idx = manager.get_index_daily('000300', 5)
    if not idx.empty:
        print(f"   成功: {len(idx)} 条")
    
    manager.close()
    print("\n✅ 测试完成")
