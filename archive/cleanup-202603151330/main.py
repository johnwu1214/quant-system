#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化交易系统 - 主程序
"""
import os
import sys
import schedule
import time
from datetime import datetime

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import get_stock_daily, get_stock_realtime, get_macd_moma, save_data
from strategies.ma_strategy import MAStrategy, RSIStrategy
from backtest import BacktestEngine
from notifier import FeishuNotifier

# ==================== 配置 ====================
# 监控列表 - 用户真实持仓
WATCH_LIST = [
    {"code": "603960", "name": "克莱机电", "shares": 1500, "cost": 17.41},
    {"code": "600938", "name": "中国海油", "shares": 300, "cost": 0.201},
    {"code": "600329", "name": "达仁堂", "shares": 500, "cost": 41.37},
    {"code": "002737", "name": "葵花药业", "shares": 2500, "cost": 14.82},
]

# 关注股票（无持仓）
WATCH_ONLY = [
    {"code": "603639", "name": "应流股份"},
    {"code": "300662", "name": "杰恩设计"},
    {"code": "601006", "name": "大秦铁路"},
]

# 初始资金
INITIAL_CAPITAL = 100000

# 飞书 Webhook（替换为你的）
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")


# ==================== 核心功能 ====================

def analyze_stock(stock_code: str, stock_name: str) -> dict:
    """分析单只股票"""
    print(f"\n📊 分析 {stock_name} ({stock_code})...")
    
    # 获取日线数据
    df = get_stock_daily(stock_code, 30)
    if df.empty:
        return {"code": stock_code, "name": stock_name, "error": "数据获取失败"}
    
    # 保存数据
    save_data(df, stock_code)
    
    # 获取MACD指标
    macd_df = get_macd_moma(stock_code, 10)
    
    # 获取实时行情
    realtime = get_stock_realtime(stock_code)
    current_price = realtime.get('price', df.iloc[-1]['close'] if not df.empty else 0)
    
    # 均线策略
    ma_strategy = MAStrategy(5, 20)
    ma_signal = ma_strategy.get_current_signal(df)
    
    # RSI策略
    rsi_strategy = RSIStrategy(14)
    rsi_signal = rsi_strategy.get_current_signal(df)
    
    # MACD信号
    macd_signal = "未知"
    if not macd_df.empty:
        latest = macd_df.iloc[-1]
        if latest['macd'] > 0:
            macd_signal = "金叉买入"
        elif latest['macd'] < 0:
            macd_signal = "死叉卖出"
        else:
            macd_signal = "持有"
    
    # 综合信号
    final_signal = "持有"
    reason = []
    
    if "买入" in ma_signal:
        reason.append("均线金叉")
    if "卖出" in ma_signal:
        reason.append("均线死叉")
    if "买入" in rsi_signal:
        reason.append("RSI超卖")
    if "卖出" in rsi_signal:
        reason.append("RSI超买")
    if macd_signal == "金叉买入":
        reason.append("MACD金叉")
    if macd_signal == "死叉卖出":
        reason.append("MACD死叉")
    
    if reason:
        # 判断是多头还是空头
        buy_signals = sum([1 for r in reason if "金叉" in r or "超卖" in r])
        sell_signals = sum([1 for r in reason if "死叉" in r or "超买" in r])
        
        if buy_signals > sell_signals:
            final_signal = "买入"
        elif sell_signals > buy_signals:
            final_signal = "卖出"
    
    return {
        "code": stock_code,
        "name": stock_name,
        "price": current_price,
        "signal": final_signal,
        "reason": " | ".join(reason) if reason else "无明确信号",
        "ma_signal": ma_signal,
        "rsi_signal": rsi_signal,
        "macd_signal": macd_signal
    }


def run_daily_analysis():
    """每日分析任务"""
    print("\n" + "="*50)
    print(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 开始每日分析")
    print("="*50)
    
    notifier = FeishuNotifier(FEISHU_WEBHOOK)
    results = []
    
    for stock in WATCH_LIST:
        result = analyze_stock(stock["code"], stock["name"])
        results.append(result)
        
        # 计算持仓盈亏
        current_value = result.get('price', 0) * stock['shares']
        pl = current_value - stock['cost']
        pl_pct = (pl / stock['cost'] * 100) if stock['cost'] > 0 else 0
        
        print(f"  {result['name']}: {result['signal']} @ ¥{result.get('price', 0):.2f} (持仓{pl:+.0f}元, {pl_pct:+.1f}%)")
        
        # 发送信号
        if result.get('signal') in ['买入', '卖出']:
            notifier.send_trading_signal(
                stock_code=result['code'],
                stock_name=result['name'],
                signal=result['signal'],
                price=result.get('price', 0),
                strategy="MA+RSI+MACD",
                reason=result.get('reason', '')
            )
    
    # 发送每日报告
    if FEISHU_WEBHOOK:
        notifier.send_daily_report(results)
    
    print("\n✅ 每日分析完成")


def run_backtest_demo():
    """演示回测功能"""
    print("\n📈 运行回测演示...")
    
    for stock in WATCH_LIST[:1]:
        df = get_stock_daily(stock["code"], 365)
        
        strategy = MAStrategy(5, 20)
        engine = BacktestEngine(INITIAL_CAPITAL)
        result = engine.run(df, strategy)
        
        print(f"\n{stock['name']} 回测结果:")
        print(f"  总收益率: {result['total_return']:.2f}%")
        print(f"  年化收益率: {result['annual_return']:.2f}%")
        print(f"  交易次数: {result['total_trades']}")
        print(f"  胜率: {result['win_rate']:.1f}%")


def main():
    """主入口"""
    print("""
╔══════════════════════════════════════════════════════╗
║         🦞 量化交易系统 v2.0 启动中...                ║
║         数据源: MomaAPI (真实数据)                   ║
╠══════════════════════════════════════════════════════╣
║  监控持仓:                                           ║
║   • 平安银行 (000001) 800股                         ║
║   • 城建发展 (600175) 5000股                        ║
║   • 中国电信 (601728) 2000股                        ║
║   • 农业银行 (601288) 2000股                        ║
║   • 交通银行 (601328) 2000股                        ║
╚══════════════════════════════════════════════════════╝
    """)
    
    # 立即运行一次分析
    run_daily_analysis()
    
    # 回测演示
    run_backtest_demo()
    
    # 设置定时任务
    schedule.every().day.at("15:00").do(run_daily_analysis)
    schedule.every().day.at("09:00").do(run_daily_analysis)
    
    print("\n⏰ 定时任务已设置")
    print("按 Ctrl+C 退出\n")
    
    # 保持运行
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
