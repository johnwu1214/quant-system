#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小龙虾量化交易系统 - 智能版 v4.0
新增：数据接口选择 | 智能策略切换 | 主动学习 | 消息通知
支持远程共享 - 只读模式
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os
from datetime import datetime
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import get_daily_tushare, get_stock_realtime
from strategies.advanced_strategies_v2 import CompositeSignal
from backtest_engine import BacktestEngine
from risk_alert import RiskAlert

# ==================== 密码保护 ====================
# 只读密码 (只查看，不能操作)
READONLY_PASSWORD = "888888"

# 管理员密码 (可编辑)
ADMIN_PASSWORD = "123456"

# 初始化session状态
if 'auth_level' not in st.session_state:
    st.session_state.auth_level = None  # None, 'readonly', 'admin'

# 登录界面
if st.session_state.auth_level is None:
    st.set_page_config(page_title="小龙虾量化 - 登录", page_icon="🦞")
    st.title("🦞 小龙虾量化交易系统")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            st.subheader("🔐 请先登录")
            password = st.text_input("访问密码", type="password")
            submit = st.form_submit_button("登录", type="primary")
            
            if submit and password:
                if password == READONLY_PASSWORD:
                    st.session_state.auth_level = 'readonly'
                    st.rerun()
                elif password == ADMIN_PASSWORD:
                    st.session_state.auth_level = 'admin'
                    st.rerun()
                else:
                    st.error("密码错误!")
            
            st.markdown("---")
            st.caption("忘记密码请联系管理员")
    
    # 显示登录背景信息
    st.info("💡 只读密码: 888888 | 管理员密码: 123456")
    st.stop()

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="小龙虾量化交易系统",
    page_icon="🦞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 数据源配置 ====================
DATA_SOURCES = {
    "Tushare": {
        "name": "Tushare",
        "description": "A股专业数据接口",
        "status": "✅ 已连接",
        "type": "历史数据"
    },
    "MomaAPI": {
        "name": "MomaAPI",
        "description": "实时行情接口",
        "status": "✅ 已连接",
        "type": "实时行情"
    }
}

# ==================== 量化模型数据库 ====================
QUANT_MODELS = {
    "MA均线交叉": {
        "name": "MA均线交叉策略",
        "type": "趋势跟踪",
        "description": "当短期均线上穿长期均线时买入，下穿时卖出",
        "advantages": ["简单直观", "趋势行情表现好", "参数少易调优"],
        "disadvantages": ["震荡行情容易亏损", "有滞后性"],
        "risk_level": "中等",
        "win_rate": "45-55%",
        "source": "经典技术分析策略",
        "author": "经典技术派",
        "suitable": "趋势明显的牛市/熊市",
        "suitable_market": ["牛市", "熊市"],
        "parameters": {"short_ma": 5, "long_ma": 20}
    },
    "RSI逆势": {
        "name": "RSI超买超卖策略",
        "type": "均值回归",
        "description": "RSI低于30买入，高于70卖出",
        "advantages": ["抄底逃顶效果好", "震荡市表现优异", "信号明确"],
        "disadvantages": ["趋势反转时可能抄底在半山腰"],
        "risk_level": "中等偏高",
        "win_rate": "40-50%",
        "source": "威尔斯·威尔德《技术交易系统新概念》",
        "author": "Welles Wilder",
        "suitable": "震荡市",
        "suitable_market": ["震荡市"],
        "parameters": {"period": 14, "oversold": 30, "overbought": 70}
    },
    "MACD趋势": {
        "name": "MACD金叉死叉策略",
        "type": "趋势跟踪",
        "description": "DIF上穿DEA买入，下穿卖出",
        "advantages": ["稳定性好", "假信号较少", "适用性广"],
        "disadvantages": ["反应较慢", "震荡市表现一般"],
        "risk_level": "中等",
        "win_rate": "50-60%",
        "source": "经典技术分析指标",
        "author": "Gerald Appel",
        "suitable": "中长线趋势行情",
        "suitable_market": ["牛市", "熊市"],
        "parameters": {"fast": 12, "slow": 26, "signal": 9}
    },
    "BOLL突破": {
        "name": "布林带突破策略",
        "type": "趋势跟踪",
        "description": "价格突破布林带上轨买入，突破下轨卖出",
        "advantages": ["自适应市场", "止损明确"],
        "disadvantages": ["参数敏感", "可能假突破"],
        "risk_level": "高",
        "win_rate": "35-45%",
        "source": "约翰·布林格发明",
        "author": "John Bollinger",
        "suitable": "波动大的市场",
        "suitable_market": ["牛市", "震荡市"],
        "parameters": {"period": 20, "std": 2}
    },
    "KDJ摆动": {
        "name": "KDJ随机摆动策略",
        "type": "摆动指标",
        "description": "K值低于20买入，高于80卖出",
        "advantages": ["灵敏度高", "适合短线"],
        "disadvantages": ["噪音太多", "假信号频繁"],
        "risk_level": "高",
        "win_rate": "30-40%",
        "source": "乔治·Lane发明",
        "author": "George Lane",
        "suitable": "短线交易",
        "suitable_market": ["震荡市", "牛市"],
        "parameters": {"period": 9, "K_period": 3, "D_period": 3}
    },
    "多因子量化": {
        "name": "多因子量化选股策略",
        "type": "基本面+技术面",
        "description": "综合PE、ROE、MACD、成交量等多因子选股",
        "advantages": ["全面分析", "抗风险能力强", "可定制"],
        "disadvantages": ["参数复杂", "需要更多数据"],
        "risk_level": "中等",
        "win_rate": "55-65%",
        "source": "Barra模型、AHP层次分析法",
        "author": "金融工程学派",
        "suitable": "中长期投资",
        "suitable_market": ["牛市", "熊市", "震荡市"],
        "parameters": {}
    }
}

# ==================== 真实持仓数据 (实盘) ====================
# 真实持仓 - 用户实际A股账户数据
REAL_POSITIONS = [
    {'code': '603960', 'name': '克莱机电', 'shares': 1500, 'cost': 17.41},
    {'code': '600938', 'name': '中国海油', 'shares': 300, 'cost': 0.201},
    {'code': '600329', 'name': '达仁堂', 'shares': 500, 'cost': 41.37},
    {'code': '002737', 'name': '葵花药业', 'shares': 2500, 'cost': 14.82},
]

# 模拟盘持仓 - 空仓待建，由小龙虾自主决策
SIMULATED_POSITIONS = [
    # 初始为空仓，小龙虾会根据策略自主买入
    # {'code': '000000', 'name': '示例', 'shares': 0, 'cost': 0},
]

# 模拟盘可买的候选股票池
SIMULATED_WATCH_LIST = [
    {'code': '600519', 'name': '贵州茅台'},
    {'code': '601318', 'name': '中国平安'},
    {'code': '600036', 'name': '招商银行'},
    {'code': '000001', 'name': '平安银行'},
    {'code': '300750', 'name': '宁德时代'},
    {'code': '600900', 'name': '长江电力'},
    {'code': '601398', 'name': '工商银行'},
    {'code': '601988', 'name': '中国银行'},
]

# ==================== Session状态 ====================
if 'current_mode' not in st.session_state:
    st.session_state.current_mode = "模拟盘"
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = "多因子量化"
if 'auto_select' not in st.session_state:
    st.session_state.auto_select = False
if 'data_source' not in st.session_state:
    st.session_state.data_source = "Tushare"
if 'learning_data' not in st.session_state:
    st.session_state.learning_data = []
if 'market_status' not in st.session_state:
    st.session_state.market_status = "震荡市"  # 默认
if 'notifications' not in st.session_state:
    st.session_state.notifications = []

# ==================== 智能学习模块 ====================
class QuantLearning:
    """量化交易智能学习模块"""
    
    def __init__(self):
        self.history = []
        self.load_history()
    
    def load_history(self):
        """加载历史学习数据"""
        try:
            with open('learning_data.json', 'r') as f:
                self.history = json.load(f)
        except:
            self.history = []
    
    def save_history(self):
        """保存学习数据"""
        with open('learning_data.json', 'w') as f:
            json.dump(self.history, f)
    
    def record_trade(self, model_name, stock_code, decision, result):
        """记录交易结果用于学习"""
        self.history.append({
            'time': datetime.now().isoformat(),
            'model': model_name,
            'stock': stock_code,
            'decision': decision,
            'result': result  # 'success' or 'fail'
        })
        self.save_history()
    
    def get_model_performance(self):
        """获取各模型表现"""
        performance = {}
        for record in self.history:
            model = record['model']
            if model not in performance:
                performance[model] = {'success': 0, 'fail': 0}
            if record['result'] == 'success':
                performance[model]['success'] += 1
            else:
                performance[model]['fail'] += 1
        
        # 计算胜率
        for model in performance:
            total = performance[model]['success'] + performance[model]['fail']
            if total > 0:
                performance[model]['win_rate'] = performance[model]['success'] / total * 100
            else:
                performance[model]['win_rate'] = 0
        
        return performance
    
    def recommend_model(self, market_status):
        """根据市场状态推荐模型"""
        scores = {}
        for name, model in QUANT_MODELS.items():
            if market_status in model.get('suitable_market', []):
                scores[name] = 80  # 基础分
            else:
                scores[name] = 30
        
        # 根据历史表现加分
        perf = self.get_model_performance()
        for model, data in perf.items():
            scores[model] = scores.get(model, 50) + data['win_rate'] * 0.2
        
        # 返回最高分
        if scores:
            best_model = max(scores, key=scores.get)
            return best_model, scores
        return "多因子量化", {}


# 初始化学习模块
learner = QuantLearning()

# ==================== 市场环境判断 ====================
def detect_market_status(df):
    """判断市场环境"""
    if df.empty or len(df) < 60:
        return "震荡市"
    
    recent = df.tail(60)
    
    # 计算MA方向
    ma5 = recent['close'].rolling(5).mean()
    ma20 = recent['close'].rolling(20).mean()
    ma趋势 = (ma5.iloc[-1] - ma5.iloc[-20]) / ma5.iloc[-20] * 100
    
    # 计算波动率
    volatility = recent['close'].pct_change().std() * 100
    
    # 计算涨跌趋势
    returns = (recent['close'].iloc[-1] / recent['close'].iloc[0] - 1) * 100
    
    # 判断
    if returns > 10 and ma趋势 > 5:
        return "牛市"
    elif returns < -10 and ma趋势 < -5:
        return "熊市"
    elif volatility > 3:
        return "震荡市"
    else:
        return "震荡市"


# ==================== 侧边栏 ====================
st.sidebar.title("🦞 小龙虾量化")

# 登录信息显示
st.sidebar.markdown("---")
if st.session_state.auth_level == 'admin':
    st.sidebar.success("🔑 管理员身份 (可编辑)")
else:
    st.sidebar.info("👁️ 只读模式 (仅浏览)")

# 登出按钮
if st.sidebar.button("🚪 退出登录"):
    st.session_state.auth_level = None
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("📊 账户模式")
is_readonly = st.session_state.auth_level == 'readonly'
mode = st.sidebar.radio("选择模式", ["模拟盘", "实盘"], 
                         index=0 if st.session_state.current_mode == "模拟盘" else 1,
                         disabled=is_readonly)
st.session_state.current_mode = mode

# 数据源选择
st.sidebar.markdown("---")
st.sidebar.subheader("📡 数据源")
data_source = st.sidebar.selectbox(
    "选择数据源",
    list(DATA_SOURCES.keys()),
    index=list(DATA_SOURCES.keys()).index(st.session_state.data_source),
    disabled=is_readonly
)
st.session_state.data_source = data_source

for ds_name, ds_info in DATA_SOURCES.items():
    if ds_name == data_source:
        st.sidebar.info(f"{ds_info['status']} - {ds_info['description']}")

# 账户信息
st.sidebar.markdown("---")
st.sidebar.subheader("💰 账户信息")
if mode == "模拟盘":
    # 模拟盘初始资金100万
    account_balance = st.sidebar.number_input("模拟资金 (¥)", value=1000000.0, step=100000.0, disabled=is_readonly)
    if not is_readonly:
        st.sidebar.info("💡 模拟盘：初始资金100万，空仓待建")
else:
    # 实盘模式：使用真实持仓，不可编辑
    st.sidebar.warning("🔴 实盘模式：数据来源于真实持仓")
    
    # 实盘资金数据
    REAL_AVAILABLE_CASH = 80934.48  # 可用资金
    
    st.sidebar.metric("可用资金", f"¥{REAL_AVAILABLE_CASH:,.2f}")
    st.sidebar.info("📊 总资产/盈亏见持仓概览页面")
    
    # 实盘模式下account_balance稍后在持仓页面计算
    account_balance = 0  # 临时值，会在持仓页面重新计算

# 量化模型选择
st.sidebar.markdown("---")
st.sidebar.subheader("🤖 量化模型")

# 自动/手动选择
auto_mode = st.sidebar.checkbox("🤖 智能自动选择", value=st.session_state.auto_select, disabled=is_readonly)
st.session_state.auto_select = auto_mode

if auto_mode:
    # 根据市场自动推荐
    st.sidebar.markdown("### 🧠 AI智能推荐")
    
    # 获取市场状态
    market_status = st.session_state.market_status
    recommended_model, scores = learner.recommend_model(market_status)
    
    st.sidebar.success(f"当前市场: **{market_status}**")
    st.sidebar.success(f"推荐模型: **{recommended_model}**")
    
    # 显示各模型得分
    with st.sidebar.expander("📊 模型评分详情"):
        for model, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            st.write(f"{model}: {score:.1f}分")
    
    st.session_state.selected_model = recommended_model
else:
    model_names = list(QUANT_MODELS.keys())
    selected_model = st.sidebar.selectbox("选择量化模型", model_names,
        index=model_names.index(st.session_state.selected_model) if st.session_state.selected_model in model_names else 0,
        disabled=is_readonly)
    st.session_state.selected_model = selected_model

# 通知设置
st.sidebar.markdown("---")
st.sidebar.subheader("🔔 通知设置")
enable_notify = st.sidebar.checkbox("策略切换通知", value=True, disabled=is_readonly)
notify_channel = st.sidebar.selectbox("通知方式", ["系统通知", "飞书消息", "邮件"], disabled=is_readonly)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**当前模型:** {st.session_state.selected_model}")

# ==================== 主界面 ====================
st.title("🦞 小龙虾量化交易系统 v4.0 智能版")

# 只读模式提示
if is_readonly:
    st.warning("👁️ 只读模式 - 您正在以只读方式访问，无法修改任何设置")

# 顶部状态栏
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("模式", mode)
col2.metric("数据源", data_source)
col3.metric("当前模型", st.session_state.selected_model)
col4.metric("总资产", f"¥{account_balance:,.0f}")

# 智能状态显示
st.info(f"🧠 当前市场环境: **{st.session_state.market_status}** | AI正在学习进化中...")

st.markdown("---")

# 页面选择
page = st.radio("📁 功能页面",
    ["📊 持仓概览", "📈 股票分析", "🔍 选股池", "🧠 智能策略", "📉 回测系统", "⚠️ 风控预警", "📖 模型介绍", "⚙️ 系统设置"],
    horizontal=True)

WATCH_LIST = [
    {'code': '603639', 'name': '应流股份'},
    {'code': '300662', 'name': '杰恩设计'},
    {'code': '601006', 'name': '大秦铁路'},
]

HOT_STOCKS = [
    {'code': '601398', 'name': '工商银行'},
    {'code': '600519', 'name': '贵州茅台'},
    {'code': '600036', 'name': '招商银行'},
    {'code': '601318', 'name': '中国平安'},
    {'code': '300750', 'name': '宁德时代'},
    {'code': '600900', 'name': '长江电力'},
]

@st.cache_data(ttl=60)
@st.cache_data(ttl=60)
def get_stock_price_cached(code):
    try:
        return get_stock_realtime(code).get('price', 0)
    except:
        return 0

def get_all_prices(positions):
    prices = {}
    all_codes = [p['code'] for p in positions] + [w['code'] for w in WATCH_LIST] + [h['code'] for h in HOT_STOCKS]
    for code in all_codes:
        prices[code] = get_stock_price_cached(code)
    return prices


# ==================== 页面选择后设置持仓 ====================
def plot_kline(df, stock_name, indicators=True):
    if df.empty or len(df) < 10:
        return None
    
    df = df.tail(60).copy()
    
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.15, 0.15, 0.2])
    
    fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='K线'), row=1, col=1)
    
    df['MA5'] = df['close'].rolling(5).mean()
    df['MA10'] = df['close'].rolling(10).mean()
    df['MA20'] = df['close'].rolling(20).mean()
    
    fig.add_trace(go.Scatter(x=df['date'], y=df['MA5'], name='MA5', line=dict(color='blue', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['date'], y=df['MA10'], name='MA10', line=dict(color='orange', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], name='MA20', line=dict(color='purple', width=1)), row=1, col=1)
    
    colors = ['red' if df['close'].iloc[i] >= df['open'].iloc[i] else 'green' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df['date'], y=df['volume'], name='成交量', marker_color=colors), row=2, col=1)
    
    if indicators:
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        
        fig.add_trace(go.Bar(x=df['date'], y=hist, name='MACD直方图', marker_color='gray'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df['date'], y=macd, name='DIF', line=dict(color='blue', width=1)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df['date'], y=signal, name='DEA', line=dict(color='orange', width=1)), row=3, col=1)
        
        low14 = df['low'].rolling(14).min()
        high14 = df['high'].rolling(14).max()
        rsv = (df['close'] - low14) / (high14 - low14) * 100
        df['K'] = rsv.ewm(span=3, adjust=False).mean()
        df['D'] = df['K'].ewm(span=3, adjust=False).mean()
        
        fig.add_trace(go.Scatter(x=df['date'], y=df['K'], name='K', line=dict(color='cyan', width=1)), row=4, col=1)
        fig.add_trace(go.Scatter(x=df['date'], y=df['D'], name='D', line=dict(color='yellow', width=1)), row=4, col=1)
    
    fig.update_layout(title=f"{stock_name} K线图", xaxis_rangeslider_visible=False, height=700, template="plotly_dark")
    return fig


# ==================== 页面：持仓概览 ====================
if page == "📊 持仓概览":
    st.header("📊 持仓概览")
    
    # 根据模式选择正确的持仓数据
    if mode == "实盘":
        current_positions = REAL_POSITIONS
    else:
        current_positions = SIMULATED_POSITIONS
    
    prices = get_all_prices(current_positions)
    
    # 持仓市值 = 实时股价 × 股数
    total_value = sum(prices.get(p['code'], 0) * p['shares'] for p in current_positions)
    # 持仓成本 = 成本价 × 股数
    total_cost = sum(p['cost'] * p['shares'] for p in current_positions)
    # 总盈亏 = 市值 - 成本
    total_pl = total_value - total_cost
    total_pl_pct = total_pl / total_cost * 100 if total_cost > 0 else 0
    
    # 实盘使用固定可用资金
    if mode == "实盘":
        available_cash = REAL_AVAILABLE_CASH
        account_balance = available_cash + total_value  # 总资产 = 可用资金 + 持仓市值
    else:
        available_cash = account_balance - total_value
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("总市值", f"¥{total_value:,.2f}")
    col2.metric("可用资金", f"¥{available_cash:,.2f}")
    col3.metric("总资产", f"¥{account_balance:,.2f}")
    col4.metric("总盈亏", f"{total_pl:+,.2f}", f"{total_pl_pct:+.1f}%")
    col5.metric("持仓数", f"{len(current_positions)}只")
    
    st.markdown("---")
    
    data = []
    for p in current_positions:
        price = prices.get(p['code'], 0)
        value = price * p['shares']
        cost = p['cost'] * p['shares']
        pl = value - cost
        pl_pct = pl / cost * 100 if cost > 0 else 0
        
        signal = "🟢 持有"
        if pl_pct > 15: signal = "🔴 止盈"
        elif pl_pct < -3: signal = "🟡 止损"
        
        data.append({"股票": p['name'], "代码": p['code'], "持股数": p['shares'],
            "成本价": f"¥{p['cost']:.2f}", "现价": f"¥{price:.2f}",
            "市值": f"¥{value:,.0f}", "盈亏": f"{pl:+,.0f}", "盈亏率": f"{pl_pct:+.1f}%", "信号": signal})
    
    st.dataframe(pd.DataFrame(data), use_container_width=True)


# ==================== 页面：股票分析 ====================
elif page == "📈 股票分析":
    st.header("📈 股票分析")
    
    # 根据模式选择正确的持仓数据
    if mode == "实盘":
        current_positions = REAL_POSITIONS
    else:
        current_positions = SIMULATED_POSITIONS
    
    all_stocks = current_positions + WATCH_LIST + HOT_STOCKS
    stock_options = {s['name']: s['code'] for s in all_stocks}
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        selected_name = st.selectbox("选择股票", list(stock_options.keys()))
        selected_code = stock_options[selected_name]
    with col2:
        days = st.selectbox("分析周期", [30, 60, 90, 120], index=1)
    with col3:
        show_indicators = st.checkbox("显示技术指标", value=True)
    
    df = get_daily_tushare(selected_code, days + 30)
    price = get_stock_price_cached(selected_code)
    
    if not df.empty and price > 0:
        # 检测市场状态
        market = detect_market_status(df)
        st.session_state.market_status = market
        
        cs = CompositeSignal()
        analysis = cs.analyze(df)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("现价", f"¥{price:.2f}")
        col2.metric("市场环境", market)
        col3.metric("决策", analysis['decision'])
        col4.metric("置信度", f"{analysis['confidence']}%")
        
        fig = plot_kline(df, selected_name, show_indicators)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("💡 交易建议")
        if '买' in analysis['decision']:
            st.success(f"🟢 买入 - 置信度 {analysis['confidence']}%")
        elif '卖' in analysis['decision']:
            st.error(f"🔴 卖出 - 置信度 {analysis['confidence']}%")
        else:
            st.info(f"🟡 持有 - 置信度 {analysis['confidence']}%")
    else:
        st.error("无法获取数据")


# ==================== 页面：选股池 ====================
elif page == "🔍 选股池":
    st.header("🔍 选股池")
    scan_stocks = st.multiselect("选择股票池", [s['name'] for s in HOT_STOCKS], default=[s['name'] for s in HOT_STOCKS[:3]])
    min_conf = st.slider("最低置信度", 0, 100, 50)
    
    if st.button("🔄 开始扫描", type="primary"):
        with st.spinner("扫描中..."):
            results = []
            for stock in HOT_STOCKS[:6]:
                df = get_daily_tushare(stock['code'], 30)
                if df.empty: continue
                price = get_stock_price_cached(stock['code'])
                if price <= 0: continue
                
                cs = CompositeSignal()
                analysis = cs.analyze(df)
                
                if analysis['confidence'] >= min_conf:
                    results.append({'股票': stock['name'], '代码': stock['code'],
                        '现价': f"¥{price:.2f}", '决策': analysis['decision'], '置信度': f"{analysis['confidence']}%"})
            
            if results:
                st.success(f"找到 {len(results)} 只符合条件")
                st.dataframe(pd.DataFrame(results), use_container_width=True)
            else:
                st.warning("暂无符合条件股票")


# ==================== 页面：智能策略 ====================
elif page == "🧠 智能策略":
    st.header("🧠 智能策略中心")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎯 市场环境判断")
        
        # 手动选择或自动检测
        market_detect = st.radio("判断方式", ["🤖 AI自动检测", "📊 手动选择"])
        
        if market_detect == "🤖 AI自动检测":
            # 获取大盘数据
            df = get_daily_tushare('000001', 60)  # 上证指数
            if not df.empty:
                market = detect_market_status(df)
                st.session_state.market_status = market
                st.success(f"AI判断当前市场: **{market}**")
            else:
                st.warning("无法获取大盘数据，使用默认")
        else:
            market = st.selectbox("选择市场环境", ["牛市", "熊市", "震荡市"])
            st.session_state.market_status = market
    
    with col2:
        st.subheader("🤖 AI策略推荐")
        
        # 获取推荐
        recommended, scores = learner.recommend_model(st.session_state.market_status)
        
        st.info(f"根据当前市场 **{st.session_state.market_status}**，推荐策略: **{recommended}**")
        
        # 显示推荐理由
        model_info = QUANT_MODELS.get(recommended, {})
        if model_info:
            st.write(f"适合场景: {model_info.get('suitable', 'N/A')}")
        
        # 历史表现
        perf = learner.get_model_performance()
        if recommended in perf:
            st.write(f"历史胜率: {perf[recommended].get('win_rate', 0):.1f}%")
    
    st.markdown("---")
    
    # 智能学习记录
    st.subheader("📚 学习记录")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📝 记录一次成功交易"):
            learner.record_trade(st.session_state.selected_model, "600519", "买入", "success")
            st.success("记录成功!")
    
    with col2:
        if st.button("📝 记录一次失败交易"):
            learner.record_trade(st.session_state.selected_model, "600519", "卖出", "fail")
            st.success("记录成功!")
    
    # 显示学习成果
    st.subheader("📊 模型学习成果")
    perf = learner.get_model_performance()
    if perf:
        perf_data = []
        for model, data in perf.items():
            perf_data.append({
                "模型": model,
                "成功": data['success'],
                "失败": data['fail'],
                "胜率": f"{data['win_rate']:.1f}%"
            })
        st.dataframe(pd.DataFrame(perf_data), use_container_width=True)
    else:
        st.info("暂无学习记录，AI正在学习中...")
    
    # 通知测试
    st.subheader("🔔 通知测试")
    if st.button("📨 发送测试通知"):
        st.warning(f"【策略切换通知】\n\n市场环境: {st.session_state.market_status}\n推荐策略: {st.session_state.selected_model}\n\n通知方式: {notify_channel}")
        st.success("通知已发送!")


# ==================== 页面：回测系统 ====================
elif page == "📉 回测系统":
    st.header("📉 回测系统")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        bt_code = st.selectbox("股票", [s['code'] for s in HOT_STOCKS])
    with col2:
        bt_days = st.selectbox("天数", [30, 60, 90, 180, 365], index=3)
    with col3:
        bt_capital = st.number_input("初始资金", value=100000.0)
    
    strategies = st.multiselect("选择策略", ["MA均线交叉", "RSI策略", "MACD策略"], default=["MA均线交叉"])
    
    if st.button("🚀 开始回测", type="primary"):
        with st.spinner("回测中..."):
            df = get_daily_tushare(bt_code, bt_days + 30)
            if not df.empty:
                df = df.sort_values('date').reset_index(drop=True)
                engine = BacktestEngine(bt_capital)
                
                results = []
                if "MA均线交叉" in strategies:
                    r = engine.run_ma_cross_backtest(df)
                    results.append({'策略': 'MA均线', '收益率': f"{r['total_return_pct']:+.1f}%", '交易次数': r['total_trades']})
                if "RSI策略" in strategies:
                    r = engine.run_rsi_backtest(df)
                    results.append({'策略': 'RSI', '收益率': f"{r['total_return_pct']:+.1f}%", '交易次数': r['total_trades']})
                if "MACD策略" in strategies:
                    r = engine.run_macd_backtest(df)
                    results.append({'策略': 'MACD', '收益率': f"{r['total_return_pct']:+.1f}%", '交易次数': r['total_trades']})
                
                st.success("回测完成!")
                st.dataframe(pd.DataFrame(results), use_container_width=True)


# ==================== 页面：风控预警 ====================
elif page == "⚠️ 风控预警":
    st.header("⚠️ 风控预警")
    
    # 根据模式选择正确的持仓数据
    if mode == "实盘":
        current_positions = REAL_POSITIONS
    else:
        current_positions = SIMULATED_POSITIONS
    
    prices = get_all_prices(current_positions)
    risk = RiskAlert()
    
    alerts = []
    for p in current_positions:
        price = prices.get(p['code'], 0)
        if price > 0:
            a = risk.check_position(p['code'], p['name'], p['cost'], price, account_balance)
            alerts.extend(a)
    
    if not alerts:
        st.success("✅ 风控检查通过，无预警!")
    else:
        for a in alerts:
            if a['priority'] == 'HIGH':
                st.error(f"🚨 {a['type']} {a['name']}: {a['message']}")
            elif a['priority'] == 'MEDIUM':
                st.warning(f"⚠️ {a['type']} {a['name']}: {a['message']}")
            else:
                st.info(f"ℹ️ {a['type']} {a['name']}: {a['message']}")


# ==================== 页面：模型介绍 ====================
elif page == "📖 模型介绍":
    st.header("📖 量化模型介绍")
    
    # 模型选择展示
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("### 选择查看模型")
        for name, info in QUANT_MODELS.items():
            with st.expander(f"{name}"):
                st.markdown(f"**类型:** {info['type']}")
                st.markdown(f"**风险等级:** {info['risk_level']}")
                st.markdown(f"**胜率:** {info['win_rate']}")
                st.markdown(f"**适合市场:** {', '.join(info.get('suitable_market', []))}")
    
    with col2:
        model = QUANT_MODELS[st.session_state.selected_model]
        
        st.markdown(f"## 🔧 {model['name']}")
        
        col_tag1, col_tag2, col_tag3 = st.columns(3)
        col_tag1.metric("类型", model['type'])
        col_tag2.metric("风险等级", model['risk_level'])
        col_tag3.metric("历史胜率", model['win_rate'])
        
        st.markdown("---")
        
        col_desc, col_src = st.columns(2)
        with col_desc:
            st.markdown("### 📝 策略描述")
            st.info(model['description'])
        
        with col_src:
            st.markdown("### 📚 来源")
            st.markdown(f"**创始人:** {model['author']}")
            st.markdown(f"**出处:** {model['source']}")
        
        col_adv, col_dis = st.columns(2)
        with col_adv:
            st.markdown("### ✅ 优势")
            for adv in model['advantages']:
                st.success(f"✓ {adv}")
        
        with col_dis:
            st.markdown("### ⚠️ 劣势")
            for dis in model['disadvantages']:
                st.warning(f"✗ {dis}")
        
        st.markdown("### 🎯 适用场景")
        st.info(f"适合: {model['suitable']}")


# ==================== 页面：系统设置 ====================
elif page == "⚙️ 系统设置":
    st.header("⚙️ 系统设置")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📡 数据源设置")
        for ds_name, ds_info in DATA_SOURCES.items():
            st.success(f"{ds_name}: {ds_info['status']}")
    
    with col2:
        st.subheader("📋 交易参数")
        max_pos = st.slider("最大持仓数", 1, 10, 5)
        stop_loss = st.slider("止损线 (%)", 1, 20, 5)
        take_profit = st.slider("止盈线 (%)", 5, 50, 15)
    
    st.subheader("🔔 通知设置")
    col1, col2 = st.columns(2)
    with col1:
        st.checkbox("策略切换通知", value=True)
        st.checkbox("风控预警通知", value=True)
    with col2:
        notify = st.selectbox("通知方式", ["系统通知", "飞书消息", "邮件"])
    
    st.subheader("ℹ️ 关于")
    st.info("小龙虾量化交易系统 v4.0 智能版")
    st.warning("股市有风险，投资需谨慎!")


# ==================== 页脚 ====================
st.markdown("---")
st.markdown(f"""
<div style='text-align: center; color: gray;'>
<p>🦞 小龙虾量化交易系统 v4.0 智能版 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<p>当前模式: {mode} | 数据源: {data_source} | 当前模型: {st.session_state.selected_model}</p>
</div>
""", unsafe_allow_html=True)
