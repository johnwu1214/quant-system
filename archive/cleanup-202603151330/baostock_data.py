#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baostock 数据源集成
免费开源的A股历史数据源，主数据源
"""
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 尝试导入 baostock
try:
    import baostock as bs
    BAOSTOCK_AVAILABLE = True
except ImportError:
    BAOSTOCK_AVAILABLE = False
    print("⚠️ Baostock 未安装，请运行: pip install baostock")


class BaostockDataFetcher:
    """Baostock 数据获取器"""
    
    def __init__(self):
        self.available = BAOSTOCK_AVAILABLE
        self.logged_in = False
        if self.available:
            self._login()
    
    def _login(self):
        """登录 Baostock"""
        if not self.logged_in:
            lg = bs.login()
            if lg.error_code == '0':
                self.logged_in = True
                print("✅ Baostock 登录成功")
            else:
                print(f"⚠️ Baostock 登录失败: {lg.error_msg}")
    
    def _convert_code(self, stock_code: str) -> str:
        """转换股票代码格式"""
        if stock_code.startswith("6"):
            return f"sh.{stock_code}"
        elif stock_code.startswith(("0", "3")):
            return f"sz.{stock_code}"
        return stock_code
    
    def get_stock_daily(self, stock_code: str, days: int = 30) -> List[Dict]:
        """获取日线数据"""
        if not self.available or not self.logged_in:
            return []
        
        try:
            symbol = self._convert_code(stock_code)
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days+30)).strftime("%Y-%m-%d")
            
            rs = bs.query_history_k_data_plus(
                code=symbol,
                fields="date,code,open,high,low,close,volume,amount",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3"  # 不复权
            )
            
            data_list = []
            while rs.error_code == '0' and rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                return []
            
            import pandas as pd
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": row["date"],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                    "amount": float(row["amount"]) if row["amount"] else 0
                })
            
            return result[-days:]
            
        except Exception as e:
            print(f"⚠️ 获取 {stock_code} 日线数据失败: {e}")
            return []
    
    def get_realtime_quote(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """获取实时行情（通过最新日线模拟）"""
        if not self.available or not self.logged_in:
            return {}
        
        result = {}
        for code in stock_codes:
            daily_data = self.get_stock_daily(code, 1)
            if daily_data:
                latest = daily_data[-1]
                result[code] = {
                    "code": code,
                    "price": latest["close"],
                    "open": latest["open"],
                    "high": latest["high"],
                    "low": latest["low"],
                    "close": latest["close"],
                    "volume": latest["volume"],
                    "date": latest["date"]
                }
        
        return result
    
    def get_index_daily(self, index_code: str = "000300", days: int = 30) -> List[Dict]:
        """获取指数日线"""
        if not self.available or not self.logged_in:
            return []
        
        try:
            # 指数代码映射
            index_map = {
                "000300": "sh.000300",  # 沪深300
                "000001": "sh.000001",  # 上证指数
                "399001": "sz.399001",  # 深证成指
                "399006": "sz.399006",  # 创业板指
            }
            
            symbol = index_map.get(index_code, f"sh.{index_code}")
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days+30)).strftime("%Y-%m-%d")
            
            rs = bs.query_history_k_data_plus(
                code=symbol,
                fields="date,code,open,high,low,close,volume",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3"
            )
            
            data_list = []
            while rs.error_code == '0' and rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                return []
            
            import pandas as pd
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": row["date"],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"])
                })
            
            return result[-days:]
            
        except Exception as e:
            print(f"⚠️ 获取指数 {index_code} 数据失败: {e}")
            return []
    
    def get_stock_info(self, stock_code: str) -> Dict:
        """获取股票基本信息"""
        # Baostock 不直接提供股票基本信息，返回最近日线数据作为替代
        daily_data = self.get_stock_daily(stock_code, 1)
        if daily_data:
            latest = daily_data[-1]
            return {
                "code": stock_code,
                "date": latest["date"],
                "close": latest["close"],
                "open": latest["open"],
                "high": latest["high"],
                "low": latest["low"],
            }
        return {}
    
    def logout(self):
        """登出 Baostock"""
        if self.logged_in:
            bs.logout()
            self.logged_in = False


# 全局实例
_fetcher = None

def get_fetcher() -> BaostockDataFetcher:
    """获取全局数据获取器"""
    global _fetcher
    if _fetcher is None:
        _fetcher = BaostockDataFetcher()
    return _fetcher


# 统一接口
def get_stock_daily_bs(code: str, days: int = 30) -> List[Dict]:
    """统一接口：获取日线数据"""
    fetcher = get_fetcher()
    return fetcher.get_stock_daily(code, days)


def get_realtime_bs(codes: List[str]) -> Dict[str, Dict]:
    """统一接口：获取实时行情"""
    fetcher = get_fetcher()
    return fetcher.get_realtime_quote(codes)


def get_index_daily_bs(index_code: str = "000300", days: int = 30) -> List[Dict]:
    """统一接口：获取指数日线"""
    fetcher = get_fetcher()
    return fetcher.get_index_daily(index_code, days)


# 测试
if __name__ == "__main__":
    print("=" * 50)
    print("🧪 Baostock 数据获取测试")
    print("=" * 50)
    
    fetcher = BaostockDataFetcher()
    
    if fetcher.available and fetcher.logged_in:
        # 测试股票日线
        print("\n📊 获取日线数据...")
        daily = fetcher.get_stock_daily("600519", 5)
        print(f"   茅台(600519): {len(daily)}条数据")
        if daily:
            d = daily[-1]
            print(f"   最新: {d['date']} 收盘价 ¥{d['close']:.2f}")
        
        # 测试指数
        print("\n📈 获取指数数据...")
        index_data = fetcher.get_index_daily("000300", 5)
        print(f"   沪深300: {len(index_data)}条数据")
        if index_data:
            d = index_data[-1]
            print(f"   最新: {d['date']} 收盘 {d['close']:.2f}")
        
        # 测试多股票实时行情
        print("\n💰 获取实时行情...")
        quotes = fetcher.get_realtime_quote(['603960', '600938', '600329', '002737'])
        for code, data in quotes.items():
            print(f"   {code}: ¥{data['price']:.2f}")
        
        fetcher.logout()
    
    print("\n✅ Baostock 测试完成")
