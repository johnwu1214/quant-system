#!/usr/bin/env python3
import os, json, re, sys
from datetime import datetime, timedelta
from pathlib import Path
import anthropic

BASE    = Path('/root/quant-system')
BL_PATH = BASE / 'risk_blacklist.json'
WL_PATH = BASE / 'watch_list.json'
LOG_DIR = BASE / 'logs'
LOG_DIR.mkdir(exist_ok=True)

_cfg         = json.loads(Path('/root/quant-system/config.json').read_text())
MINIMAX_KEY  = _cfg['minimax_api_key']
MINIMAX_BASE = 'https://api.minimaxi.com/anthropic'
MODEL        = 'MiniMax-M2.7-highspeed'

import requests as _requests

HIGH_KW = ['立案调查','强制退市','破产','债务违约','重大违规','证监会处罚','欺诈','虚假陈述','被迫停牌']
MED_KW  = ['业绩下滑','亏损','商誉减值','诉讼','质押','股权转让','实控人变更','重组失败','延期']
PERF_KW = ['净利润','营业收入','归母净利','扣非净利','同比下降','同比减少']

def _log(msg):
    ts  = datetime.now().strftime('%H:%M:%S')
    day = datetime.now().strftime('%Y%m%d')
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_DIR / f'risk_scan_{day}.log', 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def _extract_text(response):
    parts = []
    for block in response.content:
        if hasattr(block, 'type') and block.type == 'text':
            parts.append(block.text)
    return ''.join(parts).strip()

def analyze_with_m27(code, title, summary):
    prompt = f"""你是A股量化交易风险评估专家。分析以下公告并返回JSON（不要多余文字）：

股票代码: {code}
公告标题: {title}
公告摘要: {summary}

返回格式：
{{"risk_level":"high/medium/low","action":"clear/reduce/hold","target_pct":0.5,"reason":"原因","confidence":0.9}}

标准：high+clear=净利润降>30%或立案；high+reduce=净利润降10-30%或商誉减值；medium+reduce=净利润降5-10%；low+hold=正面或无影响"""
    try:
        _resp = _requests.post(
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
        _data = _resp.json()
        raw = ''
        for _block in _data.get('content', []):
            if _block.get('type') == 'text':
                raw += _block.get('text', '')
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            result = json.loads(m.group())
            result.update({'code':code,'title':title,'scanned_at':datetime.now().isoformat()})
            return result
    except Exception as e:
        _log(f"M2.7调用失败 {code}: {e}")
    return {'code':code,'risk_level':'unknown','action':'hold','target_pct':1,'reason':'调用失败','confidence':0}

def fetch_announcements(code, days=3):
    import akshare as ak
    results = []
    cutoff  = datetime.now() - timedelta(days=days)
    try:
        df = ak.stock_news_em(symbol=code)
        for _, row in df.iterrows():
            try:
                pub = datetime.strptime(str(row['发布时间'])[:10], '%Y-%m-%d')
                if pub < cutoff:
                    continue
            except Exception:
                pass
            results.append({'title':str(row.get('新闻标题','')),'summary':str(row.get('新闻内容',''))[:300]})
    except Exception as e:
        _log(f"stock_news_em失败 {code}: {e}")
    _log(f"  [{code}] 拉取新闻 {len(results)} 条")
    return results[:8]

def quick_flag(text):
    for kw in HIGH_KW:
        if kw in text: return 'high'
    if any(kw in text for kw in PERF_KW) or any(kw in text for kw in MED_KW):
        return 'medium'
    return 'low'

def load_watch_list():
    codes = set()
    try:
        data = json.loads(WL_PATH.read_text(encoding='utf-8'))
        if isinstance(data, list):
            # 直接是列表格式
            for item in data:
                codes.add(str(item.get('symbol', item.get('code','')) if isinstance(item,dict) else item))
        elif isinstance(data, dict):
            # selector_codes 字段是纯代码列表
            for c in data.get('selector_codes', []):
                codes.add(str(c))
            # stocks 字段是对象列表
            for item in data.get('stocks', []):
                if isinstance(item, dict):
                    codes.add(str(item.get('symbol', item.get('code',''))))
            # watch_list 字段
            for c in data.get('watch_list', []):
                codes.add(str(c))
    except Exception as e:
        _log(f"读取watch_list失败: {e}")

    # 始终包含当前持仓
    pos_path = BASE / 'positions.json'
    if pos_path.exists():
        try:
            raw = json.loads(pos_path.read_text(encoding='utf-8'))
            codes.update(raw.get('holdings', raw).keys())
        except Exception:
            pass

    # 过滤掉非股票代码（纯数字6位）
    codes = {c for c in codes if c and c.isdigit() and len(c) == 6}
    return list(codes)

def scan():
    _log("=" * 50)
    _log(f"风险扫描开始 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    codes = load_watch_list()
    _log(f"扫描标的: {len(codes)} 只")
    blacklist = {}
    if BL_PATH.exists():
        try:
            raw = json.loads(BL_PATH.read_text(encoding='utf-8'))
            # 兼容新格式 {"date":..,"blacklist":{}} 和旧格式 {code: {...}}
            if 'blacklist' in raw and isinstance(raw['blacklist'], dict):
                blacklist = raw['blacklist']
            else:
                # 旧格式：过滤掉非股票代码的键
                blacklist = {k: v for k, v in raw.items()
                             if isinstance(v, dict) and 'action' in v}
        except Exception:
            pass
    updated = 0
    for code in codes:
        news = fetch_announcements(code, days=3)
        if not news:
            continue
        for item in news:
            text = item['title'] + ' ' + item['summary']
            flag = quick_flag(text)
            if flag == 'low':
                continue
            _log(f"  [{code}] 关键词命中({flag}): {item['title'][:40]}")
            result = analyze_with_m27(code, item['title'], item['summary'])
            if result['risk_level'] in ('high','medium') and result['action'] != 'hold':
                blacklist[code] = result
                _log(f"  {code} -> {result['action']} ({result['risk_level']}) | {result['reason']}")
                try:
                    from weixin_notify import send_weixin
                    send_weixin(f"⚠️ 风险警报\n股票：{code}\n操作：{result['action']}\n等级：{result['risk_level']}\n原因：{result['reason']}")
                except Exception as te:
                    _log(f"  Telegram推送失败: {te}")
                updated += 1
                break
    output = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "blacklist": blacklist
    }
    BL_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    _log(f"扫描完成 | 风险标的: {updated} 只 | 黑名单共 {len(blacklist)} 条")
    _log("=" * 50)
    return blacklist

if __name__ == '__main__':
    result = scan()
    if result:
        print("\n当前风险黑名单:")
        bl = result.get('blacklist', result)
        for code, info in bl.items():
            if isinstance(info, dict) and 'action' in info:
                print(f"  {code}: {info['action']} ({info['risk_level']}) - {info['reason']}")
    else:
        print("无风险标的")