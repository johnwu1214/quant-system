import json
import os
from datetime import datetime

STATE_FILE = "portfolio_state.json"

def load_state():
    """启动时读取上次持仓状态"""
    if not os.path.exists(STATE_FILE):
        # 第一次运行，创建初始状态
        state = {
            "cash": 100000.0,
            "positions": {},
            "trade_log": [],
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        save_state(state)
        print(f"📂 首次运行，初始化账户: ¥100,000")
        return state
    
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        state = json.load(f)
    
    pos_count = len(state.get('positions', {}))
    cash = state.get('cash', 0)
    print(f"📂 读取持仓记录: {pos_count}只持仓 | 现金¥{cash:,.2f}")
    return state

def save_state(state):
    """每次交易后保存状态"""
    state['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def add_position(state, symbol, shares, price):
    """买入：更新持仓和现金"""
    cost = shares * price
    if state['cash'] < cost:
        print(f"❌ 资金不足: 需要¥{cost:.2f}, 现金¥{state['cash']:.2f}")
        return False
    
    if symbol in state['positions']:
        # 已有持仓：计算加权平均成本
        old = state['positions'][symbol]
        total_shares = old['shares'] + shares
        avg_cost = (old['shares'] * old['cost'] + shares * price) / total_shares
        state['positions'][symbol] = {
            'shares': total_shares,
            'cost': round(avg_cost, 4)
        }
    else:
        state['positions'][symbol] = {
            'shares': shares,
            'cost': price
        }
    
    state['cash'] -= cost
    state['trade_log'].append({
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'action': 'BUY',
        'symbol': symbol,
        'shares': shares,
        'price': price,
        'amount': cost
    })
    save_state(state)
    print(f"✅ 买入记录已保存: {symbol} {shares}股 @ ¥{price}")
    return True

def remove_position(state, symbol, price):
    """卖出：清除持仓，计算盈亏"""
    if symbol not in state['positions']:
        print(f"❌ 无持仓: {symbol}")
        return False
    
    pos = state['positions'][symbol]
    shares = pos['shares']
    cost = pos['cost']
    revenue = shares * price
    pnl = revenue - shares * cost
    pnl_pct = (price - cost) / cost * 100
    
    state['cash'] += revenue
    del state['positions'][symbol]
    
    state['trade_log'].append({
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'action': 'SELL',
        'symbol': symbol,
        'shares': shares,
        'price': price,
        'amount': revenue,
        'pnl': round(pnl, 2),
        'pnl_pct': round(pnl_pct, 2)
    })
    save_state(state)
    print(f"✅ 卖出记录已保存: {symbol} {shares}股 @ ¥{price} "
          f"盈亏{pnl_pct:+.2f}% ({pnl:+.2f}元)")
    return True

def print_portfolio(state, current_prices: dict):
    """打印当前持仓状态"""
    print(f"\n{'='*50}")
    print(f"📋 持仓状态 | {datetime.now().strftime('%H:%M:%S')}")
    
    total_market_value = 0
    for symbol, pos in state['positions'].items():
        price = current_prices.get(symbol, pos['cost'])
        market_value = pos['shares'] * price
        pnl_pct = (price - pos['cost']) / pos['cost'] * 100
        pnl_amt = (price - pos['cost']) * pos['shares']
        total_market_value += market_value
        
        icon = '🟢' if pnl_pct >= 0 else '🔴'
        print(f"{icon} {symbol}: {pos['shares']}股 @ "
              f"成本¥{pos['cost']:.2f}/现¥{price:.2f} "
              f"({pnl_pct:+.2f}% / {pnl_amt:+.2f}元)")
    
    total_assets = state['cash'] + total_market_value
    print(f"💵 现金: ¥{state['cash']:,.2f} | "
          f"市值: ¥{total_market_value:,.2f} | "
          f"总资产: ¥{total_assets:,.2f}")
    print(f"{'='*50}\n")
