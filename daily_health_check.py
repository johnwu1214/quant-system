#!/usr/bin/env python3
"""daily_health_check.py - 每日系统体检（自动识别交易日）"""
import json, sys, subprocess, re
from datetime import datetime, date, timedelta
from pathlib import Path

sys.path.insert(0, '/root/quant-system')
import requests
from weixin_notify import send_weixin

BASE        = Path('/root/quant-system')
LOG_DIR     = BASE / 'logs'
TODAY       = date.today().strftime('%Y%m%d')
TODAY_STR   = date.today().strftime('%Y-%m-%d')
NOW         = datetime.now()
SNAPSHOT    = BASE / f'.pool_snapshot_{TODAY}.json'
YESTERDAY_SNAPSHOT = BASE / f'.pool_snapshot_{(date.today()-timedelta(days=1)).strftime("%Y%m%d")}.json'
CONFIG      = json.loads((BASE / 'config.json').read_text(encoding='utf-8'))
MINIMAX_KEY = CONFIG['minimax_api_key']

def log(msg):
    print(f"[{NOW.strftime('%H:%M:%S')}] {msg}")

# ── 判断交易日 ──
def is_trade_day():
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        trade_dates = df['trade_date'].astype(str).tolist()
        return TODAY_STR in trade_dates
    except Exception as e:
        log(f"交易日判断失败: {e}，默认继续执行")
        return True

# ── 账户数据 ──
def load_portfolio():
    try:
        return json.loads((BASE / 'portfolio_state.json').read_text(encoding='utf-8'))
    except:
        return {}

# ── 实时价格 ──
def get_price(code):
    try:
        prefix = 'sh' if code.startswith('6') else 'sz'
        r = requests.get(
            f'https://hq.sinajs.cn/list={prefix}{code}',
            headers={'Referer': 'https://finance.sina.com.cn'}, timeout=5)
        parts = r.text.split('"')[1].split(',')
        if len(parts) > 3 and parts[3]:
            return float(parts[3])
    except:
        pass
    return None

# ── 系统运行状态 ──
def check_module(log_file_name, name):
    lf = LOG_DIR / log_file_name
    if lf.exists() and lf.stat().st_size > 100:
        t = datetime.fromtimestamp(lf.stat().st_mtime).strftime('%H:%M')
        return f"✅ {name:<10} 正常 ({t})"
    return f"❌ {name:<10} 未运行"

# ── 大盘状态 ──
def get_market():
    try:
        import akshare as ak
        df = ak.stock_zh_index_daily(symbol='sh000300')
        closes = df['close'].tail(22).tolist()
        cur, ma20 = closes[-1], sum(closes[-20:])/20
        thresh = ma20 * 0.98
        ok = cur >= thresh
        return cur, ma20, ok, f"{'正常' if ok else '偏弱'} {cur:.0f} vs MA20×0.98={thresh:.0f}"
    except:
        return None, None, None, "获取失败"

# ── 股票池变动 ──
def get_pool_changes():
    try:
        wl = json.loads((BASE / 'watch_list.json').read_text(encoding='utf-8'))
        current_pool = set(str(s) for s in wl.get('selector_codes', []))
        signal_date  = wl.get('signal_date', 'unknown')
        updated_at   = wl.get('updated_at', 'unknown')

        # 保存今日快照
        SNAPSHOT.write_text(json.dumps(list(current_pool), ensure_ascii=False), encoding='utf-8')

        # 对比昨日快照
        added, removed = [], []
        if YESTERDAY_SNAPSHOT.exists():
            yesterday_pool = set(json.loads(YESTERDAY_SNAPSHOT.read_text(encoding='utf-8')))
            added   = list(current_pool - yesterday_pool)
            removed = list(yesterday_pool - current_pool)

        return current_pool, added, removed, signal_date, updated_at
    except Exception as e:
        return set(), [], [], 'unknown', str(e)

# ── 今日交易 ──
def get_today_trades(portfolio):
    all_trades = portfolio.get('trade_log', portfolio.get('trades', []))
    return [t for t in all_trades if str(t.get('time', t.get('date', ''))).startswith(TODAY_STR)]

# ── holding_check 结果 ──
def get_ai_signals():
    lf = LOG_DIR / f'holding_check_{TODAY}.log'
    if not lf.exists():
        return []
    results = []
    for line in lf.read_text(encoding='utf-8').splitlines():
        if '建议:' in line and '分析失败' not in line:
            results.append(line[10:70])
    return results

# ── MiniMax 总评 ──
def ai_summary(portfolio, today_trades, market_ok, added, removed):
    try:
        positions  = portfolio.get('positions', {})
        total      = portfolio.get('total_assets', 0)
        cash       = portfolio.get('cash', 0)
        pos_pct    = (1 - cash/total)*100 if total else 0
        pool_change = f"股票池新增{len(added)}只移除{len(removed)}只" if (added or removed) else "股票池无变动"
        prompt = (
            f"量化系统日报：总资产¥{total:.0f}，持仓{len(positions)}只，"
            f"仓位{pos_pct:.0f}%，大盘{'偏弱禁止买入' if not market_ok else '正常'}，"
            f"今日交易{len(today_trades)}笔，{pool_change}。"
            f"持仓：{', '.join(positions.keys()) if positions else '空仓'}。"
            f"请用一句话（35字以内）给出今日操盘总评和明日核心建议，专业简洁。"
        )
        resp = requests.post(
            'https://api.minimaxi.com/anthropic/v1/messages',
            headers={'Content-Type':'application/json',
                     'x-api-key': MINIMAX_KEY,
                     'anthropic-version':'2023-06-01'},
            json={'model':'MiniMax-M2.7-highspeed',
                  'max_tokens':2048,
                  'thinking':{'type':'enabled','budget_tokens':256},
                  'messages':[{'role':'user','content':prompt}]},
            timeout=30
        )
        for block in resp.json().get('content', []):
            if block.get('type') == 'text':
                return block['text'].strip()
    except Exception as e:
        log(f"MiniMax 总评失败: {type(e).__name__}: {e}")
    return "AI分析暂不可用，请人工判断。"

def main():
    log("=" * 50)
    log(f"每日体检开始 {TODAY_STR}")

    if not is_trade_day():
        log(f"今天({TODAY_STR})非交易日，跳过体检")
        return

    portfolio    = load_portfolio()
    positions    = portfolio.get('positions', {})
    cash         = portfolio.get('cash', 0)
    # 动态计算总资产（用实时价格，不用旧缓存 current_price）
    _pos_val = 0
    for _code, _pos in positions.items():
        _live = get_price(_code)
        _price = _live if _live else _pos.get('current_price', _pos.get('cost', 0))
        _pos_val += _pos.get('shares', 0) * _price
    total     = round(cash + _pos_val, 2)
    net_value = round(total / 100000, 4)
    pos_pct      = (1 - cash/total)*100 if total else 0
    today_trades = get_today_trades(portfolio)
    buy_n        = sum(1 for t in today_trades if t.get('action')=='BUY')
    sell_n       = sum(1 for t in today_trades if t.get('action')=='SELL')

    # 持仓明细
    holding_lines, total_pnl = [], 0
    for code, pos in positions.items():
        cost   = pos.get('cost', 0)
        shares = pos.get('shares', 0)
        price  = get_price(code) or pos.get('current_price', cost)
        pnl    = (price - cost) * shares
        pct    = (price - cost)/cost*100 if cost else 0
        total_pnl += pnl
        e = '📈' if pnl >= 0 else '📉'
        holding_lines.append(f"{e} {code} {shares}股 | 成本{cost:.2f}→现价{price:.2f} | {pct:+.1f}% | {pnl:+.0f}元")

    # 今日交易
    trade_lines = []
    for t in today_trades[-5:]:
        act    = t.get('action','')
        sym    = t.get('symbol', t.get('code',''))
        pr     = t.get('price',0)
        sh     = t.get('shares',0)
        pnl    = t.get('pnl',0)
        reason = str(t.get('reason',''))[:12]
        e      = '🟢' if act=='BUY' else '🔴'
        trade_lines.append(f"{e} {act} {sym} {sh}股@{pr:.2f} {reason}{f' {pnl:+.0f}元' if pnl else ''}")

    # 系统状态
    status_lines = [
        check_module(f'trading_{TODAY}.log',      '日内交易'),
        check_module(f'risk_scan_{TODAY}.log',     '风险扫描'),
        check_module(f'holding_check_{TODAY}.log', '持仓体检'),
        check_module(f'selector_{TODAY}.log',      '选股更新'),
        check_module(f'perf_calc_{TODAY}.log',     '绩效统计'),
    ]
    try:
        daemon_ok = subprocess.run(['pgrep','-f','_daemon_notify'],
                                   capture_output=True).returncode == 0
        status_lines.append(f"{'✅' if daemon_ok else '❌'} 微信守护进程  {'在线' if daemon_ok else '离线'}")
    except:
        status_lines.append("❓ 微信守护进程  未知")

    # 大盘
    mkt_price, ma20, market_ok, mkt_desc = get_market()

    # 股票池变动
    pool, added, removed, sig_date, upd_at = get_pool_changes()
    pool_lines = [f"📦 股票池: {len(pool)}只 | 信号日期: {sig_date}"]
    if added:
        pool_lines.append(f"🆕 新增: {', '.join(added)}")
    if removed:
        pool_lines.append(f"➖ 移除: {', '.join(removed)}")
    if not added and not removed:
        pool_lines.append("  今日无变动")

    # 风险预警
    risk_lines = [f"{'🔴' if not market_ok else '✅'} 大盘: {mkt_desc}"]
    seen = set()
    for sig in get_ai_signals():
        code_key = sig[:10]
        if ('reduce' in sig or 'exit' in sig) and code_key not in seen:
            seen.add(code_key)
            risk_lines.append(f"⚠️ {sig}")
    try:
        bl = json.loads((BASE/'risk_blacklist.json').read_text(encoding='utf-8'))
        codes = list(bl.get('blacklist', {}).keys())
        if codes:
            risk_lines.append(f"🚫 黑名单: {', '.join(codes)}")
    except:
        pass

    # MiniMax 总评
    log("调用 MiniMax 生成总评...")
    summary = ai_summary(portfolio, today_trades, market_ok, added, removed)

    # 组装报告
    sections = [
        f"📋 量化系统日报 {NOW.strftime('%m-%d')}",
        "━━━ 一、账户概况 ━━━",
        f"💰 总资产: ¥{total:,.0f}  净值: {net_value:.4f}",
        f"📊 现金: ¥{cash:,.0f}({100-pos_pct:.0f}%)  仓位: {pos_pct:.0f}%",
        f"📈 持仓浮盈: {total_pnl:+,.0f}元",
        "",
        "━━━ 二、持仓明细 ━━━",
    ] + (holding_lines if holding_lines else ["  当前空仓"]) + [
        "",
        "━━━ 三、今日交易 ━━━",
    ] + (trade_lines if trade_lines else ["  今日无交易"]) + [
        f"  合计: 买入{buy_n}笔  卖出{sell_n}笔",
        "",
        "━━━ 四、系统状态 ━━━",
    ] + status_lines + [
        "",
        "━━━ 五、股票池动态 ━━━",
    ] + pool_lines + [
        "",
        "━━━ 六、风险预警 ━━━",
    ] + risk_lines + [
        "",
        "━━━ 七、AI总评 ━━━",
        f"💡 {summary}",
        "",
        f"🕐 {NOW.strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    msg = '\n'.join(sections)
    send_weixin(msg)
    (LOG_DIR / f'health_check_{TODAY}.log').write_text(msg, encoding='utf-8')
    log("体检完成，微信已推送")

if __name__ == '__main__':
    main()
