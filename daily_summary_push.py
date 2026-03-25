#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
daily_summary_push.py - 收盘汇总推送
读取 portfolio_state.json + 实时价格 → 计算浮盈 → 微信推送
"""
import sys
import os
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from data_manager import get_realtime_price
from weixin_notify import send_weixin
from performance_tracker import calc_performance, save_performance, append_nav_history

PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio_state.json")

def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"cash": 0, "positions": {}}

def push_summary():
    state = load_portfolio()
    cash = state.get("cash", 0)
    positions = state.get("positions", {})

    if not positions:
        send_weixin("📊 收盘汇总\n暂无持仓")
        return

    # 获取实时价格并计算浮盈
    stock_lines = []
    total_pnl = 0.0
    total_value = cash

    for code, pos in positions.items():
        shares = pos.get("shares", 0)
        cost = pos.get("cost", 0)
        try:
            current_price = get_realtime_price(code)
        except Exception:
            current_price = pos.get("current_price", cost)

        value = shares * current_price
        cost_total = shares * cost
        pnl = value - cost_total
        pnl_pct = (pnl / cost_total * 100) if cost_total > 0 else 0

        total_pnl += pnl
        total_value += value

        sign = "+" if pnl >= 0 else ""
        stock_lines.append(
            f"{code}: {sign}{pnl_pct:.1f}% ¥{pnl:+.2f}"
        )

    # 计算净值（假设初始100万）
    initial = 1000000.0
    nav = total_value / initial

    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M:%S")

    message = (
        f"📊 收盘汇总 {today}\n"
        f"━━━━━━━━━━━━━\n"
        f"净值：{nav:.4f}\n"
        f"总资产：¥{total_value:,.2f}\n"
        f"现金：¥{cash:,.2f}\n"
        f"持仓浮盈：¥{total_pnl:+,.2f}\n"
        f"━━━━━━━━━━━━━\n"
        + "\n".join(stock_lines) + "\n"
        f"━━━━━━━━━━━━━\n"
        f"🕐 {now_time}"
    )

    send_weixin(message)
    # 保存绩效 + 净值历史
    try:
        perf = calc_performance()
        save_performance(perf)
        append_nav_history()
    except Exception as e:
        send_weixin(f"⚠️ 绩效保存失败: {e}")

if __name__ == "__main__":
    push_summary()
