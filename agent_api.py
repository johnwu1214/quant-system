#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent_api.py - Quant Agent 指令接口
用法: python3 agent_api.py <action> [args]
"""
import json, sys, os
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio_state.json")

def load_portfolio():
    with open(PORTFOLIO_FILE, encoding="utf-8") as f:
        return json.load(f)

def cmd_portfolio():
    """显示持仓"""
    s = load_portfolio()
    pos = s.get("positions", {})
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"===== 持仓状态 {now} =====")
    if not pos:
        print("当前无持仓")
    else:
        total_cost = 0
        total_val  = 0
        for code, v in pos.items():
            shares  = v.get("shares", 0)
            cost    = v.get("cost", 0)
            cur     = v.get("current_price", cost)
            pnl     = (cur - cost) * shares
            pnl_pct = (cur - cost) / cost * 100 if cost else 0
            status  = "盈利" if pnl >= 0 else "亏损"
            total_cost += cost * shares
            total_val  += cur * shares
            print(f"{code}: {shares}股 成本{cost:.3f} 现价{cur:.2f} {status}{abs(pnl):.2f}({pnl_pct:+.2f}%)")
    print(f"现金: {s.get('cash', 0):.2f}")
    positions_val = sum(v.get("current_price", v.get("cost", 0)) * v.get("shares", 0)
                        for v in pos.values())
    print(f"总资产: {s.get('cash', 0) + positions_val:.2f}")

def cmd_pnl():
    """今日盈亏"""
    s   = load_portfolio()
    log = s.get("trade_log", [])
    today = date.today().strftime("%Y-%m-%d")
    trades = [t for t in log if t.get("time", "").startswith(today)]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"===== 今日交易 {now} =====")
    if not trades:
        print("今日暂无交易记录")
        return
    total_pnl = 0
    for t in trades:
        action = t.get("action", "")
        code   = t.get("symbol") or t.get("code", "")
        price  = t.get("price", 0)
        shares = t.get("shares", 0)
        pnl    = t.get("pnl", 0)
        reason = t.get("reason", "")
        if action == "BUY":
            print(f"买入 {code}: {shares}股 @ {price:.2f}")
        elif action == "SELL":
            status = "盈" if pnl >= 0 else "亏"
            print(f"卖出 {code}: {shares}股 @ {price:.2f} {status}{abs(pnl):.2f} {reason}")
            total_pnl += pnl
    if total_pnl != 0:
        status = "盈利" if total_pnl >= 0 else "亏损"
        print(f"今日已实现{status}: {total_pnl:+.2f}")

def cmd_risk():
    """止损检查"""
    sys.path.insert(0, BASE_DIR)
    import risk_manager_v2
    alerts = risk_manager_v2.check_all_positions(send_alert=False)
    if not alerts:
        print("所有持仓风控正常，未触发止损")
    else:
        for a in alerts:
            print(f"警告 {a['code']}: 现价{a['current']} 止损价{a['stop_price']} 亏损{a['loss']:.2f}")

def cmd_blacklist(args):
    """黑名单管理"""
    sys.path.insert(0, BASE_DIR)
    import blacklist_manager
    if len(args) >= 2 and args[0] == "add":
        code = args[1]
        reason = " ".join(args[2:]) if len(args) > 2 else "手动加入"
        blacklist_manager.add(code, reason=reason, days=30)
    elif len(args) >= 2 and args[0] == "remove":
        blacklist_manager.remove(args[1])
    elif args[0] == "list":
        bl = blacklist_manager.list_all()
        if not bl:
            print("黑名单为空")
        else:
            print(f"===== 黑名单 ({len(bl)}只) =====")
            for code, info in bl.items():
                print(f"{code}: {info.get('reason','')} 到期{info.get('expire_at','')}")
    else:
        print("用法: blacklist add/remove/list [code]")

def cmd_status():
    """系统状态"""
    import subprocess
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"===== 系统状态 {now} =====")
    r = subprocess.run("ps aux | grep -E 'intraday|openclaw' | grep -v grep",
                       shell=True, capture_output=True, text=True)
    procs = r.stdout.strip()
    if procs:
        for line in procs.split("\n"):
            parts = line.split()
            if len(parts) > 10:
                print(f"运行中: {parts[10]} PID:{parts[1]}")
    else:
        print("交易程序未运行")
    s = load_portfolio()
    pos = s.get("positions", {})
    print(f"持仓数量: {len(pos)} 只")
    print(f"现金余额: {s.get('cash', 0):.2f}")

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("用法: python3 agent_api.py <portfolio|pnl|risk|status|blacklist>")
        sys.exit(0)
    cmd = args[0]
    if cmd == "portfolio":
        cmd_portfolio()
    elif cmd == "pnl":
        cmd_pnl()
    elif cmd == "risk":
        cmd_risk()
    elif cmd == "status":
        cmd_status()
    elif cmd == "blacklist":
        cmd_blacklist(args[1:])
    else:
        print(f"未知指令: {cmd}")
