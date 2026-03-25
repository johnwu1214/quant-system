#!/usr/bin/env python3
"""holding_check.py - 持仓 MiniMax 新闻体检"""
import json, sys, re
import blacklist_manager
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '/root/quant-system')
import requests
import akshare as ak
from weixin_notify import send_weixin

BASE    = Path('/root/quant-system')
CONFIG  = json.loads((BASE / 'config.json').read_text(encoding='utf-8'))
LOG_DIR = BASE / 'logs'
LOG_DIR.mkdir(exist_ok=True)

MINIMAX_KEY = CONFIG['minimax_api_key']
MODEL       = 'MiniMax-M2.7-highspeed'
# 使用 requests 直接调用，避免 SDK header 兼容问题

def log(msg):
    ts   = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    today = datetime.now().strftime('%Y%m%d')
    with open(LOG_DIR / f'holding_check_{today}.log', 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def get_news(code):
    try:
        df     = ak.stock_news_em(symbol=code)
        titles = df['新闻标题'].head(5).tolist()
        return ' | '.join(titles)
    except Exception as e:
        return f"无法获取新闻: {e}"

def analyze(code, cost, current_price, pnl_pct, news_text):
    try:
        prompt = (
            f"股票{code}，成本价{cost:.2f}，当前盈亏约{pnl_pct:.1f}%。\n"
            f"最新新闻：{news_text}\n"
            f"请从持仓管理角度判断操作，只输出JSON不要其他文字：\n"
            '{\"action\":\"hold或reduce或exit\",\"reason\":\"一句话原因\",\"urgency\":\"low或medium或high\"}'
        )
        resp = requests.post(
            'https://api.minimaxi.com/anthropic/v1/messages',
            headers={
                'Content-Type': 'application/json',
                'x-api-key': MINIMAX_KEY,
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': MODEL,
                'max_tokens': 2048,
                'thinking': {'type': 'enabled', 'budget_tokens': 1024},
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=30
        )
        data = resp.json()
        text = ''
        for block in data.get('content', []):
            if block.get('type') == 'text':
                text += block.get('text', '')
        m = re.search(r'\{.*?\}', text, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as e:
        log(f"[{code}] MiniMax 调用失败: {type(e).__name__}: {e}")
    return {"action": "hold", "reason": "分析失败，默认持有", "urgency": "low"}

def main():
    log("=" * 40)
    log(f"持仓体检开始 {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    portfolio = json.loads((BASE / 'portfolio_state.json').read_text(encoding='utf-8'))
    positions = portfolio.get('positions', {})

    if not positions:
        log("当前无持仓，退出")
        return

    results      = []
    reduce_count = 0
    exit_count   = 0

    for code, pos in positions.items():
        cost          = pos.get('cost', pos.get('avg_cost', 0))
        current_price = pos.get('current_price', cost)
        pnl_pct       = (current_price - cost) / cost * 100 if cost else 0
        shares        = pos.get('shares', 0)

        log(f"[{code}] 成本:{cost:.2f} 现价:{current_price:.2f} 盈亏:{pnl_pct:.1f}% {shares}股")
        news   = get_news(code)
        log(f"[{code}] 新闻: {news[:80]}...")
        result = analyze(code, cost, current_price, pnl_pct, news)
        result.update({'code': code, 'pnl_pct': pnl_pct, 'shares': shares})
        results.append(result)

        action = result.get('action', 'hold')
        log(f"[{code}] 建议: {action} | {result.get('reason','')}")
        if action == 'reduce':
            reduce_count += 1
        elif action == 'exit':
            exit_count += 1
            # 自动闭环：exit + urgency=high → 写入黑名单 → 下次 intraday 触发卖出
            urgency = result.get('urgency', 'low')
            if urgency == 'high':
                reason = result.get('reason', '持仓体检建议清仓')
                ok = blacklist_manager.add_to_blacklist(code, reason=reason, source='holding_check_auto')
                if ok:
                    log(f"[{code}] 🚨 已自动加入黑名单（urgency=high），下次intraday将触发卖出")
            else:
                log(f"[{code}] ⚠️ 建议清仓但 urgency={urgency}，需人工确认")

    emoji_map = {'hold': '✅', 'reduce': '⚠️', 'exit': '🔴'}
    lines = [
        f"📊 持仓体检 {datetime.now().strftime('%m-%d %H:%M')}",
        "━━━━━━━━━━━━━━"
    ]
    for r in results:
        e = emoji_map.get(r['action'], '❓')
        lines.append(f"{r['code']}: {e} {r['action'].upper()}")
        lines.append(f"  盈亏 {r['pnl_pct']:.1f}% | {r.get('reason','')}")
    lines += ["━━━━━━━━━━━━━━", f"💡 建议: 减仓{reduce_count}只 清仓{exit_count}只"]

    send_weixin('\n'.join(lines))
    log("微信推送完成")
    log(f"体检完成 | 共{len(results)}只 | 减仓{reduce_count} 清仓{exit_count}")

if __name__ == '__main__':
    main()