#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
intelligence_scanner.py - 情报扫描系统（方案A AKShare免费版）
公告接口: stock_zh_a_disclosure_report_cninfo (巨潮资讯)
新闻接口: stock_news_em (东方财富)
每日15:35收盘后自动运行
"""

import akshare as ak
import json
import time
import requests
from datetime import date, datetime
from pathlib import Path

# ── 配置区 ──
BASE_DIR        = Path("/root/quant-system")
WATCH_LIST_PATH = BASE_DIR / "watch_list.json"
PORTFOLIO_PATH  = BASE_DIR / "portfolio_state.json"
LOG_PATH        = BASE_DIR / "intelligence_log.json"

# 微信推送配置 (OpenClaw Gateway)
GATEWAY_URL   = "http://127.0.0.1:18789"
GATEWAY_TOKEN = "35ec305d5d232b3b1ed0238962daefc427ef46b2e28e55cb"
TARGET_USER   = "o9cq80yJxHbRLO8tbYzQlJu3IoJI@im.wechat"
ACCOUNT_ID    = "46dec126a996-im-bot"

# 风险关键词
HIGH_RISK_KEYWORDS = [
    '立案调查','收到警示函','被迫停产','破产','强制执行',
    '冻结','吊销','财务造假','欺诈','重大违法'
]
MEDIUM_RISK_KEYWORDS = [
    '质押','大幅下降','亏损','违规','诉讼','仲裁',
    '业绩预亏','资产减值','债务违约','解除质押'
]

# ── 工具函数 ──

def load_stock_list():
    stocks = set()
    try:
        wl = json.loads(Path(WATCH_LIST_PATH).read_text())
        stocks.update(wl.get("stocks", []))
    except Exception as e:
        print(f"[WARN] watch_list读取失败: {e}")
    try:
        ps = json.loads(Path(PORTFOLIO_PATH).read_text())
        stocks.update(ps.get("positions", {}).keys())
    except Exception as e:
        print(f"[WARN] portfolio读取失败: {e}")
    return list(stocks)

def safe_fetch(func, *args, retries=3, delay=4, **kwargs):
    for i in range(retries):
        try:
            result = func(*args, **kwargs)
            time.sleep(delay)
            return result
        except Exception as e:
            print(f"[WARN] 第{i+1}次调用失败: {e}，{delay*(i+1)}s后重试")
            time.sleep(delay * (i + 1))
    return None

def send_weixin(title, content, priority="normal"):
    """通过微信推送消息 - 使用队列方式"""
    try:
        from weixin_notify import send_weixin as wx_send
        success = wx_send(content, title, priority)
        if success:
            print(f"[微信] 消息已加入队列: {title}")
        else:
            print(f"[微信] 加入队列失败: {title}")
    except Exception as e:
        print(f"[ERROR] 微信推送失败: {e}")

# ── 核心扫描 ──

def scan_announcements(stock, today_str):
    """使用巨潮资讯接口扫描公告"""
    result = {
        "stock": stock, "risk_level": "normal",
        "risk_keywords_hit": [], "notice_count": 0,
        "titles": [], "error": None
    }
    df = safe_fetch(ak.stock_zh_a_disclosure_report_cninfo, symbol=stock)
    if df is None or df.empty:
        result["error"] = "公告接口无数据"
        return result

    # 筛选今日公告（公告时间字段格式: 2026-03-15 00:00:00）
    today_df = df[df['公告时间'].astype(str).str.startswith(today_str)]
    result["notice_count"] = len(today_df)

    if today_df.empty:
        print(f"  [{stock}] 今日无新公告")
        return result

    titles    = today_df['公告标题'].astype(str).tolist()
    result["titles"] = titles
    full_text = " ".join(titles)
    print(f"  [{stock}] 今日公告 {len(titles)} 条: {titles[0][:30]}...")

    # 分级风险识别
    for kw in HIGH_RISK_KEYWORDS:
        if kw in full_text:
            result["risk_level"] = "high_risk"
            result["risk_keywords_hit"].append(kw)

    if result["risk_level"] != "high_risk":
        for kw in MEDIUM_RISK_KEYWORDS:
            if kw in full_text:
                result["risk_level"] = "medium_risk"
                result["risk_keywords_hit"].append(kw)

    return result

def scan_news(stock):
    """使用东方财富接口扫描新闻情绪"""
    result = {
        "stock": stock, "news_sentiment": "neutral",
        "negative_headlines": [], "error": None
    }
    df = safe_fetch(ak.stock_news_em, symbol=stock)
    if df is None or df.empty:
        result["error"] = "新闻接口无数据"
        return result

    recent    = df['新闻标题'].astype(str).tolist()[:10]
    neg_kw    = ['下跌','暴跌','跌停','亏损','违规','处罚','风险',
                 '警示','调查','诉讼','冻结','减持','大幅下滑','爆雷']
    pos_kw    = ['涨停','大涨','增长','超预期','利好','新高',
                 '突破','中标','获批','签约','订单','拟分红']
    neg_count = sum(1 for t in recent for kw in neg_kw if kw in t)
    pos_count = sum(1 for t in recent for kw in pos_kw if kw in t)

    if neg_count >= 3:
        result["news_sentiment"] = "negative"
        result["negative_headlines"] = [
            t for t in recent if any(kw in t for kw in neg_kw)]
    elif pos_count > neg_count:
        result["news_sentiment"] = "positive"

    print(f"  [{stock}] 新闻情绪: {result['news_sentiment']} "
          f"(负面{neg_count}条/正面{pos_count}条)")
    return result

# ── 主流程 ──

def run_intelligence_scan():
    today_str = str(date.today())
    now_str   = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*50}")
    print(f"[INFO] 情报扫描启动 {now_str}")
    print(f"{'='*50}")

    stock_list = load_stock_list()
    if not stock_list:
        print("[ERROR] 股票列表为空，退出")
        return
    print(f"[INFO] 扫描标的: {stock_list}\n")

    all_results   = {}
    high_risk     = []
    medium_risk   = []
    normal_stocks = []

    for stock in stock_list:
        print(f"[SCAN] {stock} ...")
        ann  = scan_announcements(stock, today_str)
        news = scan_news(stock)

        # 合并风险等级
        final_risk = ann["risk_level"]
        if final_risk == "normal" and news["news_sentiment"] == "negative":
            final_risk = "medium_risk"

        all_results[stock] = {
            "final_risk_level": final_risk,
            "announcement": ann,
            "news": news,
            "scan_time": now_str
        }

        if final_risk == "high_risk":
            high_risk.append(stock)
        elif final_risk == "medium_risk":
            medium_risk.append(stock)
        else:
            normal_stocks.append(stock)
        print()

    # 保存日志
    log_data = {
        "scan_date": today_str,
        "scan_time": now_str,
        "summary": {
            "high_risk":   high_risk,
            "medium_risk": medium_risk,
            "normal":      normal_stocks
        },
        "details": all_results
    }
    Path(LOG_PATH).write_text(
        json.dumps(log_data, ensure_ascii=False, indent=2))
    print(f"[INFO] 日志已保存: {LOG_PATH}")

    # 构建微信推送报告
    lines = [f"📡 情报扫描 {today_str}", "─" * 28]
    if high_risk:
        lines.append("🚨 高风险（建议规避）:")
        for s in high_risk:
            kws = all_results[s]["announcement"]["risk_keywords_hit"]
            lines.append(f"  ▶ {s} 命中: {','.join(kws)}")
            for t in all_results[s]["announcement"]["titles"][:2]:
                lines.append(f"    · {t[:35]}")
    else:
        lines.append("✅ 无高风险标的")

    if medium_risk:
        lines.append("\n⚠️ 中风险（留意）:")
        for s in medium_risk:
            sent = all_results[s]["news"]["news_sentiment"]
            kws  = all_results[s]["announcement"]["risk_keywords_hit"]
            lines.append(f"  ▶ {s} | 公告:{','.join(kws) or '无'} | 新闻:{sent}")

    if normal_stocks:
        lines.append(f"\n✔️ 正常: {', '.join(normal_stocks)}")

    lines.append("─" * 28)
    msg = "\n".join(lines)
    print("\n" + msg)

    if high_risk:
        send_weixin("🚨紧急风险告警", msg, priority="high")
    else:
        send_weixin("📡每日情报扫描", msg, priority="normal")

    return log_data

if __name__ == "__main__":
    run_intelligence_scan()
