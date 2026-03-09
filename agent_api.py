#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quant Agent 数据接口层
只读接口，供 OpenClaw quant Agent Skills 调用
用法: python3 agent_api.py <action>
"""
import json
import sys
import argparse
from datetime import datetime, date
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_portfolio():
    with open(f'{BASE_DIR}/portfolio_state.json') as f:
        return json.load(f)

def load_watchlist():
    with open(f'{BASE_DIR}/watch_list.json') as f:
        return json.load(f)

# ══════════════════════════════════════
# 1. 持仓查询
# ══════════════════════════════════════
def get_portfolio():
    state = load_portfolio()
    positions = state.get('positions', {})
    cash = state.get('cash', 0)

    pos_list = []
    total_cost = 0
    for code, pos in positions.items():
        cost_total = pos['shares'] * pos['cost']
        total_cost += cost_total
        pos_list.append({
            "code": code,
            "shares": pos['shares'],
            "cost": round(pos['cost'], 3),
            "cost_total": round(cost_total, 2)
        })

    total_assets = cash + total_cost
    position_ratio = round(total_cost / total_assets * 100, 1) if total_assets > 0 else 0

    return {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "cash": round(cash, 2),
        "positions": pos_list,
        "position_count": len(pos_list),
        "total_cost": round(total_cost, 2),
        "total_assets": round(total_assets, 2),
        "position_ratio": f"{position_ratio}%",
        "cash_ratio": f"{round(100 - position_ratio, 1)}%"
    }

# ══════════════════════════════════════
# 2. 今日交易信号
# ══════════════════════════════════════
def get_signals():
    today = date.today().strftime('%Y%m%d')
    log_file = f'{BASE_DIR}/logs/trading_{today}.log'
    signals = []
    summary = []

    try:
        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if any(k in line for k in ['BUY', 'SELL', '买入', '卖出', '止损', '止盈']):
                    signals.append(line)
                if any(k in line for k in ['总资产', '现金', '持仓', '盈亏']):
                    summary.append(line)
    except FileNotFoundError:
        signals = ["今日交易日志暂未生成"]

    return {
        "date": str(date.today()),
        "signals": signals[-20:],  # 最近20条
        "summary": summary[-5:]
    }

# ══════════════════════════════════════
# 3. 风险状态
# ══════════════════════════════════════
def get_risk():
    state = load_portfolio()
    positions = state.get('positions', {})
    cash = state.get('cash', 0)

    STOP_LOSS = -0.08
    TAKE_PROFIT = 0.15
    WARNING_LINE = -0.05

    alerts = []
    warnings = []
    normal = []

    total_cost = sum(p['shares'] * p['cost'] for p in positions.values())
    total_assets = cash + total_cost
    position_ratio = total_cost / total_assets if total_assets > 0 else 0

    for code, pos in positions.items():
        cost = pos['cost']
        shares = pos['shares']
        cost_total = shares * cost
        weight = cost_total / total_assets if total_assets > 0 else 0

        item = {
            "code": code,
            "shares": shares,
            "cost": cost,
            "weight": f"{round(weight*100, 1)}%",
            "note": "需实时行情计算盈亏"
        }

        if weight > 0.15:
            alerts.append({**item, "level": "⚠️ 单股占比过高"})
        else:
            normal.append({**item, "level": "✅ 正常"})

    risk_level = "🔴 高风险" if alerts else "🟡 注意" if warnings else "🟢 正常"

    return {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "risk_level": risk_level,
        "position_ratio": f"{round(position_ratio*100, 1)}%",
        "alerts": alerts,
        "warnings": warnings,
        "normal": normal,
        "thresholds": {
            "stop_loss": f"{int(STOP_LOSS*100)}%",
            "take_profit": f"{int(TAKE_PROFIT*100)}%",
            "warning": f"{int(WARNING_LINE*100)}%"
        }
    }

# ══════════════════════════════════════
# 4. 监控列表
# ══════════════════════════════════════
def get_watchlist():
    try:
        data = load_watchlist()
        if isinstance(data, list):
            return {"date": str(date.today()), "mode": "未知", "watch_list": data}
        return {
            "date": data.get('date', ''),
            "mode": data.get('mode', ''),
            "market_regime": data.get('market_regime', ''),
            "watch_list": data.get('watch_list', []),
            "count": len(data.get('watch_list', []))
        }
    except Exception as e:
        return {"error": str(e)}

# ══════════════════════════════════════
# 5. 系统健康检查
# ══════════════════════════════════════
def get_health():
    checks = {}

    # 检查核心文件
    files = {
        "portfolio_state.json": f'{BASE_DIR}/portfolio_state.json',
        "watch_list.json": f'{BASE_DIR}/watch_list.json',
        "intraday_v4_2.py": f'{BASE_DIR}/intraday_v4_2.py',
        "stock_selector_v2.py": f'{BASE_DIR}/stock_selector_v2.py',
    }
    for name, path in files.items():
        checks[name] = "✅ 存在" if os.path.exists(path) else "❌ 缺失"

    # 检查今日日志
    today = date.today().strftime('%Y%m%d')
    log_file = f'{BASE_DIR}/logs/trading_{today}.log'
    checks["今日交易日志"] = "✅ 已生成" if os.path.exists(log_file) else "⚠️ 未生成"

    # 检查选股日志
    selector_log = f'{BASE_DIR}/logs/selector_{today}.log'
    checks["今日选股日志"] = "✅ 已生成" if os.path.exists(selector_log) else "⚠️ 未生成"

    # 读取最后更新时间
    try:
        state = load_portfolio()
        last_update = state.get('updated_at', '未知')
    except:
        last_update = "读取失败"

    return {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "files": checks,
        "portfolio_last_update": last_update,
        "status": "✅ 系统正常" if all("✅" in v for v in list(checks.values())[:4]) else "⚠️ 需要检查"
    }

# ══════════════════════════════════════
# 6. 交易历史摘要
# ══════════════════════════════════════
def get_history():
    state = load_portfolio()
    trade_log = state.get('trade_log', [])

    buy_count = sum(1 for t in trade_log if t['action'] == 'BUY')
    sell_count = sum(1 for t in trade_log if t['action'] == 'SELL')
    total_pnl = sum(t.get('pnl', 0) for t in trade_log if t['action'] == 'SELL')

    return {
        "total_trades": len(trade_log),
        "buy_count": buy_count,
        "sell_count": sell_count,
        "total_realized_pnl": round(total_pnl, 2),
        "recent_trades": trade_log[-5:],
        "created_at": state.get('created_at', ''),
        "updated_at": state.get('updated_at', '')
    }

# ══════════════════════════════════════
# 主入口
# ══════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='quant Agent 数据接口')
    parser.add_argument('action', choices=[
        'portfolio', 'signals', 'risk', 'watchlist', 'health', 'history'
    ], help='查询类型')
    args = parser.parse_args()

    actions = {
        'portfolio': get_portfolio,
        'signals':   get_signals,
        'risk':      get_risk,
        'watchlist': get_watchlist,
        'health':    get_health,
        'history':   get_history,
    }

    result = actions[args.action]()
    print(json.dumps(result, ensure_ascii=False, indent=2))
