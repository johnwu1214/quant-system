#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化系统参数优化配置
优化日期: 2026-03-04
"""
from typing import Dict, Any

# ==================== 策略参数优化 ====================

STRATEGY_PARAMS = {
    # AI 策略参数
    "ai_strategy": {
        "confidence_threshold": 0.75,        # 提升置信度阈值 (原0.7)
        "min_confidence": 0.65,              # 最低置信度
        "ensemble_weight": {
            "technical": 0.3,                 # 技术面权重
            "fundamental": 0.25,              # 基本面权重
            "sentiment": 0.2,                 # 情绪面权重
            "ai": 0.25                        # AI判断权重
        }
    },
    
    # 网格策略参数
    "grid_strategy": {
        "grid_count": 10,                     # 网格数量
        "grid_ratio": 0.02,                   # 网格间距比例 (2%)
        "stop_loss": 0.08,                    # 止损线 (8%)
        "take_profit": 0.15,                  # 止盈线 (15%)
        "rebalance_threshold": 0.1,           # 再平衡阈值
    },
    
    # 风控参数
    "risk_control": {
        "max_position": 0.2,                  # 单票最大仓位 (20%)
        "max_loss_per_trade": 0.05,           # 单笔最大亏损 (5%)
        "daily_loss_limit": 0.03,             # 日亏损限制 (3%)
        "max_drawdown": 0.15,                 # 最大回撤限制 (15%)
        "position_limit": 4,                  # 最大持仓数量
    },
    
    # 选股参数
    "stock_selection": {
        "min_market_cap": 50_000_000_000,    # 最小市值 (500亿)
        "max_market_cap": 2_000_000_000_000, # 最大市值 (2万亿)
        "min_volume": 100_000_000,            # 最小日成交额 (10亿)
        "min_turnover": 0.5,                  # 最小换手率 (0.5%)
        "exclude_st": True,                    # 排除ST股票
        "exclude_new": True,                  # 排除新股 (上市<180天)
    },
    
    # 回测参数
    "backtest": {
        "initial_capital": 100000,           # 初始资金
        "commission": 0.0003,                 # 佣金 (万三)
        "stamp_duty": 0.001,                  # 印花税 (千一，卖出)
        "slippage": 0.001,                    # 滑点 (千一)
    },
    
    # 实盘参数
    "live_trading": {
        "order_type": "limit",                # 订单类型: limit/farket
        "price_type": "qfq",                  # 前复权
        "max_retry": 3,                       # 最大重试次数
        "retry_interval": 5,                  # 重试间隔(秒)
    }
}

# ==================== 因子参数优化 ====================

FACTOR_PARAMS = {
    # 动量因子
    "momentum": {
        "short_period": 5,                    # 短期动量周期
        "medium_period": 10,                   # 中期动量周期  
        "long_period": 20,                    # 长期动量周期
        "threshold": 0.03,                     # 动量阈值
    },
    
    # 波动率因子
    "volatility": {
        "short_period": 5,
        "medium_period": 10,
        "long_period": 20,
        "lookback_periods": [5, 10, 20, 60],  # 回看周期
    },
    
    # 成交量因子
    "volume": {
        "ma_periods": [5, 10, 20],            # 均线周期
        "volume_ratio_threshold": 1.5,         # 量比阈值
    },
    
    # 技术指标参数
    "technical": {
        "ma_periods": [5, 10, 20, 30, 60],    # 均线周期
        "rsi_periods": [6, 12, 24],           # RSI周期
        "macd_fast": 12,                      # MACD快线
        "macd_slow": 26,                      # MACD慢线
        "macd_signal": 9,                     # MACD信号线
        "boll_period": 20,                     # 布林带周期
        "boll_std": 2,                         # 布林带标准差倍数
    }
}

# ==================== 优化建议 ====================

OPTIMIZATION_NOTES = """
参数优化说明 (2026-03-04):

1. 置信度阈值: 0.7 → 0.75
   - 理由: AI置信度平均0.87，提升阈值可减少假信号
   
2. 止损线: 5% → 8%  
   - 理由: 给趋势策略更多波动空间，避免被洗出

3. 最大回撤: 10% → 15%
   - 理由: 允许更大的波动以获取更多收益

4. 动量周期: 调整短期/中期/长期参数
   - 更适应A股市场特性

5. 新增因子: 筹码分布、股东户数变化
   - 增加选股精确度
"""
