#!/usr/bin/env python3
"""blacklist_manager.py - 黑名单读取模块"""
import json
from pathlib import Path
from datetime import date

BLACKLIST = Path("/root/quant-system/risk_blacklist.json")

def is_blacklisted(code):
    try:
        data  = json.loads(BLACKLIST.read_text())
        today = str(date.today())
        if data.get('date') != today:
            return False
        bl = data.get('blacklist', {})
        if code in bl:
            print(f"  🚫 {code} 在黑名单中: {bl[code]}")
            return True
        return False
    except Exception:
        return False

def add_to_blacklist(code, reason="", source="holding_check", duration_days=1):
    """将股票加入当日黑名单，intraday_v4_2.py 下次运行时自动跳过买入/触发卖出"""
    try:
        today = str(date.today())
        # 读取现有黑名单
        try:
            data = json.loads(BLACKLIST.read_text())
            if data.get('date') != today:
                data = {'date': today, 'blacklist': {}}
        except Exception:
            data = {'date': today, 'blacklist': {}}

        data['blacklist'][code] = {
            'reason': reason,
            'source': source,
            'added_at': str(date.today()),
            'duration_days': duration_days
        }
        BLACKLIST.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"  🚫 {code} 已加入黑名单: {reason[:30]}")
        return True
    except Exception as e:
        print(f"  ❌ 黑名单写入失败: {e}")
        return False


def remove_from_blacklist(code):
    """从黑名单移除指定股票"""
    try:
        data = json.loads(BLACKLIST.read_text())
        if code in data.get('blacklist', {}):
            del data['blacklist'][code]
            BLACKLIST.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            print(f"  ✅ {code} 已从黑名单移除")
            return True
        return False
    except Exception:
        return False
