#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
魔码云服 MomaAPI - 专注两大核心功能:
1. 实时行情备用源（腾讯故障时启用）
2. 涨停股过滤（选股时排除涨停股，避免追高）
"""
import requests, time, json
from datetime import datetime

TOKEN = "6C2D188A-7482-419D-905E-D146DA9964F0"
BASE = "http://api.momaapi.com"

def get_realtime(code):
    """实时行情 - 腾讯故障时的备用"""
    try:
        r = requests.get(f"{BASE}/hsrl/ssjy/{code}/{TOKEN}", timeout=5)
        if r.status_code == 200:
            d = r.json()
            return {
                "code": code, "price": d.get("p",0),
                "pct_chg": d.get("pc",0), "change": d.get("ud",0),
                "high": d.get("h",0), "low": d.get("l",0),
                "open": d.get("o",0), "pre_close": d.get("yc",0),
                "volume": d.get("v",0), "amount": d.get("cje",0),
                "turnover": d.get("hs",0), "pe": d.get("pe",0),
                "market_cap": d.get("sz",0), "source": "moma"
            }
    except: pass
    return None

def get_limit_up_codes(date=None):
    """获取今日涨停股代码列表 - 用于选股过滤"""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    try:
        r = requests.get(f"{BASE}/hslt/ztgc/{date}/{TOKEN}", timeout=8)
        if r.status_code == 200:
            data = r.json()
            # 提取纯股票代码（去掉 sh/sz 前缀）
            codes = []
            for item in data:
                dm = item.get("dm","")
                code = dm.replace("sh","").replace("sz","").replace("bj","")
                if code:
                    codes.append(code)
            return codes
    except: pass
    return []

def is_limit_up(code, date=None):
    """判断某只股票今天是否涨停"""
    codes = get_limit_up_codes(date)
    return code in codes

def get_market_sentiment(date=None):
    """市场情绪指标：今日涨停数量"""
    codes = get_limit_up_codes(date)
    count = len(codes)
    if count >= 80:
        sentiment = "极度亢奋"
    elif count >= 50:
        sentiment = "亢奋"
    elif count >= 30:
        sentiment = "偏强"
    elif count >= 15:
        sentiment = "中性"
    else:
        sentiment = "低迷"
    return {"count": count, "sentiment": sentiment, "codes": codes}
