#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AkShare 数据源集成
免费开源的A股数据源，作为备用数据源
"""
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# 尝试导入 AkShare
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    print("⚠️ AkShare 未安装，请运行: pip install akshare")


class AkShareDataFetcher:
    """AkShare 数据获取器"""
    
    def __init__(self):
        self.available = AKSHARE_AVAILABLE
        if not self.available:
            print("⚠️ AkShare 不可用，将使用备用方案")
    
    def get_stock_daily(self, stock_code: str, days: int = 30) -> List[Dict]:
        """获取日线数据"""
        if not self.available:
            return []
        
        try:
            # 转换股票代码格式
            symbol = self._convert_code(stock_code)
            
            # 获取数据
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=(datetime.now() - timedelta(days=days+30)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust="qfq"
            )
            
            # 转换为字典列表
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": row["日期"].strftime("%Y-%m-%d") if isinstance(row["日期"], datetime) else str(row["日期"]),
                    "open": float(row["开盘"]),
                    "high": float(row["最高"]),
                    "low": float(row["最低"]),
                    "close": float(row["收盘"]),
                    "volume": float(row["成交量"]),
                    "amount": float(row["成交额"]) if "成交额" in row else 0
                })
            
            return result[-days:]  # 返回最近的天数
            
        except Exception as e:
            print(f"⚠️ 获取 {stock_code} 数据失败: {e}")
            return []
    
    def _convert_code(self, stock_code: str) -> str:
        """转换股票代码格式"""
        if stock_code.startswith("6"):
            return f"{stock_code}.SH"
        elif stock_code.startswith(("0", "3")):
            return f"{stock_code}.SZ"
        return stock_code
    
    def get_realtime_quote(self, stock_code: str = None) -> List[Dict]:
        """获取实时行情"""
        if not self.available:
            return []
        
        try:
            df = ak.stock_zh_a_spot_em()
            
            result = []
            for _, row in df.iterrows():
                code = str(row["代码"])
                if stock_code and code != stock_code:
                    continue
                
                result.append({
                    "code": code,
                    "name": row["名称"],
                    "price": float(row["最新价"]) if row["最新价"] != "-" else 0,
                    "change_pct": float(row["涨跌幅"]) if row["涨跌幅"] != "-" else 0,
                    "volume": float(row["成交量"]) if row["成交量"] != "-" else 0,
                    "amount": float(row["成交额"]) if row["成交额"] != "-" else 0,
                    "amplitude": float(row["振幅"]) if row["振幅"] != "-" else 0,
                    "high": float(row["最高"]) if row["最高"] != "-" else 0,
                    "low": float(row["最低"]) if row["最低"] != "-" else 0,
                    "open": float(row["今开"]) if row["今开"] != "-" else 0,
                    "close_prev": float(row["昨收"]) if row["昨收"] != "-" else 0,
                })
                
                if stock_code:
                    break
            
            return result
            
        except Exception as e:
            print(f"⚠️ 获取实时行情失败: {e}")
            return []
    
    def get_stock_info(self, stock_code: str) -> Dict:
        """获取股票基本信息"""
        if not self.available:
            return {}
        
        try:
            symbol = self._convert_code(stock_code)
            df = ak.stock_individual_info_em(symbol=symbol)
            
            info = {}
            for _, row in df.iterrows():
                info[row["item"]] = row["value"]
            
            return info
            
        except Exception as e:
            print(f"⚠️ 获取股票信息失败: {e}")
            return {}
    
    def get_financial_data(self, stock_code: str, indicator: str = "按报告期") -> List[Dict]:
        """获取财务数据"""
        if not self.available:
            return []
        
        try:
            symbol = self._convert_code(stock_code)
            
            if "利润表" in indicator:
                df = ak.stock_financial_analysis_indicator(symbol=symbol)
            else:
                df = ak.stock_financial_abstract_ths(symbol=symbol)
            
            result = []
            for _, row in df.head(8).iterrows():  # 最近8个季度
                result.append(dict(row))
            
            return result
            
        except Exception as e:
            print(f"⚠️ 获取财务数据失败: {e}")
            return []
    
    def get_index_daily(self, index_code: str = "000300", days: int = 30) -> List[Dict]:
        """获取指数日线"""
        if not self.available:
            return []
        
        try:
            if index_code == "000300":
                df = ak.stock_zh_index_daily(symbol="sh000300")
            elif index_code == "000001":
                df = ak.stock_zh_index_daily(symbol="sh000001")
            else:
                df = ak.stock_zh_index_daily(symbol=f"sh{index_code}")
            
            result = []
            for _, row in df.tail(days).iterrows():
                result.append({
                    "date": row["date"].strftime("%Y-%m-%d") if isinstance(row["date"], datetime) else str(row["date"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"])
                })
            
            return result
            
        except Exception as e:
            print(f"⚠️ 获取指数数据失败: {e}")
            return []
    
    def get_market_sentiment(self) -> Dict:
        """获取市场情绪"""
        if not self.available:
            return {}
        
        try:
            # 涨跌停统计
            df = ak.stock_zt_pool_em(date=datetime.now().strftime("%Y%m%d"))
            
            return {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "limit_up_count": len(df),
                "limit_down_count": 0,  # 需要单独查询
                "total_stocks": 5000,  # 估算
            }
            
        except Exception as e:
            print(f"⚠️ 获取市场情绪失败: {e}")
            return {}
    
    def get_money_flow(self, stock_code: str = None, days: int = 5) -> Dict:
        """获取资金流向"""
        if not self.available:
            return {}
        
        try:
            if stock_code:
                symbol = self._convert_code(stock_code)
                df = ak.stock_individual_fund_flow(stock=symbol, market="sh" if stock_code.startswith("6") else "sz")
                
                return {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "main_inflow": float(df["今日主力净流入-净额"].iloc[0]) if len(df) > 0 else 0,
                    "main_inflow_pct": float(df["今日主力净流入-净流入占比"].iloc[0]) if len(df) > 0 else 0,
                }
            else:
                # 大盘资金流向
                df = ak.stock_fund_flow_statistics()
                return {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "total_inflow": float(df["今日净流入-净额"].sum()) if "今日净流入-净额" in df.columns else 0
                }
                
        except Exception as e:
            print(f"⚠️ 获取资金流向失败: {e}")
            return {}


# 导出统一接口
def get_stock_daily_ak(code: str, days: int = 30) -> List[Dict]:
    """统一接口：获取日线数据"""
    fetcher = AkShareDataFetcher()
    return fetcher.get_stock_daily(code, days)


def get_realtime_ak(code: str = None) -> List[Dict]:
    """统一接口：获取实时行情"""
    fetcher = AkShareDataFetcher()
    return fetcher.get_realtime_quote(code)


# 测试
if __name__ == "__main__":
    print("🧪 测试 AkShare 数据获取...")
    
    fetcher = AkShareDataFetcher()
    
    if fetcher.available:
        # 测试获取实时行情
        print("\n📊 获取实时行情...")
        quotes = fetcher.get_realtime_quote("600519")
        if quotes:
            q = quotes[0]
            print(f"   {q['name']}: ¥{q['price']:.2f} ({q['change_pct']:+.2f}%)")
        
        # 测试指数数据
        print("\n📈 获取指数数据...")
        index_data = fetcher.get_index_daily("000300", 5)
        print(f"   沪深300: {len(index_data)}条数据")
        
        # 测试资金流向
        print("\n💰 获取资金流向...")
        flow = fetcher.get_money_flow("600519")
        print(f"   主力净流入: {flow.get('main_inflow', 0):,.0f}元")
    else:
        print("   ⚠️ AkShare 未安装")
    
    print("\n✅ AkShare 数据模块测试完成")
