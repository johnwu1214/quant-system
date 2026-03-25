#!/usr/bin/env python3
"""
weekly_summary.py - 每周五收盘后综合总结
自动识别是否为周五交易日，统计本周交易/净值/系统稳定性，MiniMax生成周评
"""
import json, sys, re
from datetime import datetime, date, timedelta
from pathlib import Path

sys.path.insert(0, '/root/quant-system')
import requests
from weixin_notify import send_weixin

BASE        = Path('/root/quant-system')
LOG_DIR     = BASE / 'logs'
TODAY       = date.today()
TODAY_STR   = TODAY.strftime('%Y-%m-%d')
NOW         = datetime.now()
CONFIG      = json.loads((BASE / 'config.json').read_text(encoding='utf-8'))
MINIMAX_KEY = CONFIG['minimax_api_key']

def log(msg):
    print(f"[{NOW.strftime('%H:%M:%S')}] {msg}")

# ── 判断是否周五交易日 ──
def is_friday_tradeday():
    if TODAY.weekday() != 4:  # 0=周一 4=周五
        log(f"今天是{['周一','周二','周三','周四','周五','周六','周日'][TODAY.weekday()]}，非周五，跳过")
        return False
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        trade_dates = df['trade_date'].astype(str).tolist()
        if TODAY_STR not in trade_dates:
            log(f"今天({TODAY_STR})是周五但非交易日（节假日），跳过")
            return False
        return True
    except Exception as e:
        log(f"交易日判断失败: {e}，默认继续执行")
        return True

# ── 本周日期范围 ──
def get_week_range():
    monday = TODAY - timedelta(days=TODAY.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday

# ── 本周交易统计 ──
def get_week_trades():
    try:
        portfolio = json.loads((BASE / 'portfolio_state.json').read_text(encoding='utf-8'))
        all_trades = portfolio.get('trade_log', portfolio.get('trades', []))
        monday, friday = get_week_range()
        week_trades = []
        for t in all_trades:
            t_date = str(t.get('time', ''))[:10]
            try:
                td = datetime.strptime(t_date, '%Y-%m-%d').date()
                if monday <= td <= friday:
                    week_trades.append(t)
            except:
                pass
        return week_trades, portfolio
    except Exception as e:
        log(f"交易数据读取失败: {e}")
        return [], {}

# ── 计算胜率和盈亏比 ──
def calc_stats(trades):
    sells = [t for t in trades if t.get('action') == 'SELL' and t.get('pnl') is not None]
    if not sells:
        return 0, 0, 0, 0, 0
    wins  = [t for t in sells if t.get('pnl', 0) > 0]
    loses = [t for t in sells if t.get('pnl', 0) <= 0]
    win_rate   = len(wins) / len(sells) * 100 if sells else 0
    avg_win    = sum(t.get('pnl', 0) for t in wins)  / len(wins)  if wins  else 0
    avg_loss   = sum(t.get('pnl', 0) for t in loses) / len(loses) if loses else 0
    profit_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    total_pnl  = sum(t.get('pnl', 0) for t in sells)
    return win_rate, profit_ratio, avg_win, avg_loss, total_pnl

# ── 本周净值变化 ──
def get_week_nav():
    nav_list = []
    monday, friday = get_week_range()
    for i in range(5):
        d = monday + timedelta(days=i)
        log_file = LOG_DIR / f'health_check_{d.strftime("%Y%m%d")}.log'
        if log_file.exists():
            content = log_file.read_text(encoding='utf-8')
            m = re.search(r'净值: (\d+\.\d+)', content)
            if m:
                nav_list.append((d.strftime('%m-%d'), float(m.group(1))))
    return nav_list

# ── 本周系统稳定性 ──
def get_week_stability():
    monday, _ = get_week_range()
    crash_count  = 0
    run_days     = 0
    for i in range(5):
        d = monday + timedelta(days=i)
        if d > TODAY:
            break
        log_file = LOG_DIR / f'trading_{d.strftime("%Y%m%d")}.log'
        if log_file.exists() and log_file.stat().st_size > 0:
            run_days += 1
            content = log_file.read_text(encoding='utf-8')
            crash_count += content.count('Traceback') + content.count('Error')
    return run_days, crash_count

# ── 本周股票池变化汇总 ──
def get_week_pool_changes():
    monday, _ = get_week_range()
    all_added, all_removed = set(), set()
    prev_pool = None
    for i in range(5):
        d = monday + timedelta(days=i)
        if d > TODAY:
            break
        snap = BASE / f'.pool_snapshot_{d.strftime("%Y%m%d")}.json'
        if snap.exists():
            curr_pool = set(json.loads(snap.read_text(encoding='utf-8')))
            if prev_pool is not None:
                all_added   |= (curr_pool - prev_pool)
                all_removed |= (prev_pool - curr_pool)
            prev_pool = curr_pool
    return list(all_added), list(all_removed), prev_pool or set()

# ── MiniMax 周评 ──
def ai_week_review(week_trades, portfolio, win_rate, profit_ratio, total_pnl, nav_list, crash_count):
    try:
        positions = portfolio.get('positions', {})
        total     = portfolio.get('total_assets', 0)
        nav_str   = ' → '.join([f"{n[1]:.4f}" for n in nav_list]) if nav_list else "数据不足"
        prompt = (
            f"量化系统本周总结：总资产¥{total:.0f}，"
            f"本周交易{len(week_trades)}笔（买入{sum(1 for t in week_trades if t.get('action')=='BUY')}笔，"
            f"卖出{sum(1 for t in week_trades if t.get('action')=='SELL')}笔），"
            f"已结算盈亏¥{total_pnl:+.0f}，胜率{win_rate:.0f}%，盈亏比{profit_ratio:.1f}，"
            f"净值曲线：{nav_str}，系统报错{crash_count}次，"
            f"当前持仓：{', '.join(positions.keys()) if positions else '空仓'}。\n"
            f"请用100字以内给出本周操盘总结评价和下周核心策略建议，专业客观。"
        )
        resp = requests.post(
            'https://api.minimaxi.com/anthropic/v1/messages',
            headers={'Content-Type':'application/json',
                     'x-api-key': MINIMAX_KEY,
                     'anthropic-version':'2023-06-01'},
            json={'model':'MiniMax-M2.7-highspeed',
                  'max_tokens':1024,
                  'thinking':{'type':'enabled','budget_tokens':512},
                  'messages':[{'role':'user','content':prompt}]},
            timeout=45
        )
        for block in resp.json().get('content', []):
            if block.get('type') == 'text':
                return block['text'].strip()
    except Exception as e:
        log(f"MiniMax 周评失败: {type(e).__name__}: {e}")
    return "本周系统运行完成，建议下周继续观察大盘趋势后决策。"

def main():
    log("=" * 50)
    log(f"每周总结开始 {TODAY_STR}")

    if not is_friday_tradeday():
        return

    monday, friday = get_week_range()
    week_trades, portfolio = get_week_trades()
    win_rate, profit_ratio, avg_win, avg_loss, total_pnl = calc_stats(week_trades)
    nav_list     = get_week_nav()
    run_days, crash_count = get_week_stability()
    added, removed, curr_pool = get_week_pool_changes()
    positions    = portfolio.get('positions', {})
    total        = portfolio.get('total_assets', 0)
    cash         = portfolio.get('cash', 0)
    net_value    = portfolio.get('net_value', 1.0)

    buy_trades  = [t for t in week_trades if t.get('action') == 'BUY']
    sell_trades = [t for t in week_trades if t.get('action') == 'SELL']

    # 交易明细（最多8条）
    trade_lines = []
    for t in week_trades[-8:]:
        act = t.get('action','')
        sym = t.get('symbol', t.get('code',''))
        pr  = t.get('price', 0)
        sh  = t.get('shares', 0)
        pnl = t.get('pnl', 0)
        e   = '🟢' if act == 'BUY' else '🔴'
        pnl_str = f" {pnl:+.0f}元" if pnl else ''
        trade_lines.append(f"{e} {t.get('time','')[:10]} {act} {sym} {sh}股@{pr:.2f}{pnl_str}")

    # 净值曲线
    nav_str = '  '.join([f"{d}:{v:.4f}" for d,v in nav_list]) if nav_list else "数据不足"

    # 股票池变动
    pool_lines = [f"📦 当前股票池: {len(curr_pool)}只"]
    if added:
        pool_lines.append(f"🆕 本周新增: {', '.join(added)}")
    if removed:
        pool_lines.append(f"➖ 本周移除: {', '.join(removed)}")
    if not added and not removed:
        pool_lines.append("  本周无变动")

    log("调用 MiniMax 生成周评...")
    week_review = ai_week_review(
        week_trades, portfolio, win_rate, profit_ratio,
        total_pnl, nav_list, crash_count
    )

    sections = [
        f"📊 量化系统周报",
        f"📅 {monday.strftime('%m/%d')} - {friday.strftime('%m/%d')}",
        "",
        "━━━ 一、账户状态 ━━━",
        f"💰 总资产: ¥{total:,.0f}  净值: {net_value:.4f}",
        f"📊 现金: ¥{cash:,.0f}  持仓: {len(positions)}只",
        f"📈 净值曲线: {nav_str}",
        "",
        "━━━ 二、本周交易 ━━━",
        f"📋 共{len(week_trades)}笔 | 买入{len(buy_trades)} | 卖出{len(sell_trades)}",
        f"🎯 胜率: {win_rate:.0f}%  盈亏比: {profit_ratio:.1f}",
        f"💵 已实现盈亏: {total_pnl:+,.0f}元",
        f"📈 平均盈利: {avg_win:+.0f}元  平均亏损: {avg_loss:+.0f}元",
    ] + (trade_lines if trade_lines else ["  本周无交易记录"]) + [
        "",
        "━━━ 三、系统稳定性 ━━━",
        f"✅ 运行天数: {run_days}/5天",
        f"{'✅' if crash_count==0 else '⚠️'} 系统报错: {crash_count}次",
        "",
        "━━━ 四、股票池变动 ━━━",
    ] + pool_lines + [
        "",
        "━━━ 五、AI周评 ━━━",
        f"💡 {week_review}",
        "",
        f"🕐 {NOW.strftime('%Y-%m-%d %H:%M:%S')}",
    ]

    msg = '\n'.join(sections)
    send_weixin(msg)

    log_file = LOG_DIR / f'weekly_summary_{TODAY_STR}.log'
    log_file.write_text(msg, encoding='utf-8')
    log(f"周报完成，微信已推送，日志: {log_file}")

if __name__ == '__main__':
    main()
