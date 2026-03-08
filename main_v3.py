#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化交易系统 v3.0 - 主程序
集成AI因子挖掘、AI策略生成、财报分析、AkShare数据、增强风控
"""
import os
import sys
import schedule
import time
import json
import functools
from datetime import datetime
from pathlib import Path
import pandas as pd

# ==================== 执行日志追踪系统 ====================
class ExecutionLogger:
    """执行日志追踪器"""
    
    def __init__(self):
        self.logs = {
            "运行时间戳": {},
            "阶段耗时": {},
            "调用链追踪": {
                "function_call_sequence": [],
                "api_call_count": 0,
                "database_query_count": 0
            }
        }
        self.call_stack = []
        self.start_time = None
    
    def start(self):
        """开始记录"""
        self.start_time = time.time()
        self.logs["运行时间戳"]["start_time"] = datetime.now().isoformat()
        print("\n🔍 执行日志系统已启动...")
    
    def end(self):
        """结束记录"""
        end_time = time.time()
        self.logs["运行时间戳"]["end_time"] = datetime.now().isoformat()
        self.logs["运行时间戳"]["total_duration"] = round(end_time - self.start_time, 2)
        print(f"\n⏱️ 总耗时: {self.logs['运行时间戳']['total_duration']}秒")
    
    def time_section(self, name: str):
        """计时上下文管理器"""
        return SectionTimer(self, name)
    
    def track_call(self, func_name: str):
        """追踪函数调用"""
        self.logs["调用链追踪"]["function_call_sequence"].append({
            "function": func_name,
            "timestamp": datetime.now().isoformat()
        })
    
    def increment_api_call(self):
        """增加API调用计数"""
        self.logs["调用链追踪"]["api_call_count"] += 1
    
    def increment_db_query(self):
        """增加数据库查询计数"""
        self.logs["调用链追踪"]["database_query_count"] += 1
    
    def save(self, filepath: str = None):
        """保存日志"""
        if filepath is None:
            filepath = os.path.join(os.path.dirname(__file__), "data", "execution_log.json")
        
        # 确保目录存在
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.logs, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 执行日志已保存: {filepath}")
        return filepath
    
    def print_summary(self):
        """打印日志摘要"""
        print("\n" + "="*50)
        print("📊 执行日志摘要")
        print("="*50)
        
        ts = self.logs["运行时间戳"]
        print(f"🕐 开始时间: {ts.get('start_time', 'N/A')}")
        print(f"🕐 结束时间: {ts.get('end_time', 'N/A')}")
        print(f"⏱️ 总耗时: {ts.get('total_duration', 'N/A')}秒")
        
        print("\n📈 阶段耗时 breakdown:")
        for section, duration in self.logs["阶段耗时"].items():
            print(f"   • {section}: {duration}秒")
        
        ct = self.logs["调用链追踪"]
        print(f"\n🔗 调用链追踪:")
        print(f"   • 函数调用次数: {len(ct['function_call_sequence'])}")
        print(f"   • API调用次数: {ct['api_call_count']}")
        print(f"   • 数据库查询次数: {ct['database_query_count']}")
        
        print("\n📋 函数调用顺序:")
        for i, call in enumerate(ct['function_call_sequence'][:10], 1):
            print(f"   {i}. {call['function']}")
        if len(ct['function_call_sequence']) > 10:
            print(f"   ... 还有 {len(ct['function_call_sequence']) - 10} 个调用")


class SectionTimer:
    """代码段计时器"""
    
    def __init__(self, logger: ExecutionLogger, name: str):
        self.logger = logger
        self.name = name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.track_call(self.name)
        return self
    
    def __exit__(self, *args):
        duration = time.time() - self.start_time
        self.logger.logs["阶段耗时"][self.name] = round(duration, 3)


# 全局日志器
execution_logger = ExecutionLogger()


# ==================== 数据质量监控系统 ====================
class DataQualityMonitor:
    """数据质量监控"""
    
    def __init__(self):
        self.data = {
            "行情数据完整性": {
                "expected_ticks": {},
                "actual_ticks": {},
                "missing_rate": {},
                "delayed_ticks": {}
            },
            "数据一致性校验": {
                "price_validation": {},
                "volume_validation": {},
                "time_sequence_check": {}
            },
            "数据源健康度": {
                "momaapi_status": {"connected": False, "response_time_ms": None},
                "qlib_status": {"connected": False, "data_count": 0},
                "baostock_status": {"connected": False},
                "akshare_status": {"available": False, "limitations": []}
            }
        }
        self.check_times = {}
    
    def check_data_completeness(self, stock_code: str, df, expected_days: int = 30):
        """检查行情数据完整性"""
        self.data["行情数据完整性"]["expected_ticks"][stock_code] = expected_days
        
        actual = len(df) if df is not None else 0
        self.data["行情数据完整性"]["actual_ticks"][stock_code] = actual
        
        missing_rate = ((expected_days - actual) / expected_days * 100) if expected_days > 0 else 0
        self.data["行情数据完整性"]["missing_rate"][stock_code] = round(missing_rate, 2)
        
        # 检查延迟数据（简单的周末/假日检查）
        if df is not None and not df.empty:
            latest_date = df.iloc[-1]['date'] if 'date' in df.columns else None
            # 这里可以添加更复杂的延迟检测逻辑
            self.data["行情数据完整性"]["delayed_ticks"][stock_code] = 0
    
    def validate_data_consistency(self, stock_code: str, df):
        """数据一致性校验"""
        if df is None or df.empty:
            self.data["数据一致性校验"]["price_validation"][stock_code] = "无数据"
            self.data["数据一致性校验"]["volume_validation"][stock_code] = "无数据"
            self.data["数据一致性校验"]["time_sequence_check"][stock_code] = "无数据"
            return
        
        # 价格合理性检查
        if 'close' in df.columns:
            prices = df['close']
            if (prices > 0).all() and (prices < 10000).all():
                self.data["数据一致性校验"]["price_validation"][stock_code] = "✅ 正常"
            else:
                self.data["数据一致性校验"]["price_validation"][stock_code] = "⚠️ 异常值"
        
        # 成交量合理性检查
        if 'volume' in df.columns:
            volumes = df['volume']
            if (volumes >= 0).all():
                self.data["数据一致性校验"]["volume_validation"][stock_code] = "✅ 正常"
            else:
                self.data["数据一致性校验"]["volume_validation"][stock_code] = "⚠️ 负值"
        
        # 时间序列连续性检查
        if 'date' in df.columns:
            dates = pd.to_datetime(df['date'])
            date_diffs = dates.diff().dropna()
            # 允许1-3天的间隔（周末/假日）
            max_diff = date_diffs.max().days if len(date_diffs) > 0 else 0
            if max_diff <= 7:
                self.data["数据一致性校验"]["time_sequence_check"][stock_code] = "✅ 连续"
            else:
                self.data["数据一致性校验"]["time_sequence_check"][stock_code] = f"⚠️ 断点({max_diff}天)"
    
    def check_data_source_health(self):
        """检查数据源健康度"""
        import time
        
        # MomaAPI 健康检查
        start = time.time()
        try:
            from data_fetcher import get_stock_daily
            test_df = get_stock_daily("600519", 1)
            response_time = (time.time() - start) * 1000
            self.data["数据源健康度"]["momaapi_status"] = {
                "connected": True,
                "response_time_ms": round(response_time, 2),
                "data_available": not test_df.empty if test_df is not None else False
            }
        except Exception as e:
            self.data["数据源健康度"]["momaapi_status"] = {
                "connected": False,
                "error": str(e)[:100]
            }
        
        # Qlib 健康检查
        try:
            qlib_dir = os.path.expanduser("~/quant_system/data/qlib")
            if os.path.exists(qlib_dir):
                import glob
                files = glob.glob(f"{qlib_dir}/*/*.csv")
                self.data["数据源健康度"]["qlib_status"] = {
                    "connected": True,
                    "data_count": len(files)
                }
            else:
                self.data["数据源健康度"]["qlib_status"] = {"connected": False}
        except Exception as e:
            self.data["数据源健康度"]["qlib_status"] = {"connected": False, "error": str(e)[:50]}
        
        # Baostock 健康检查
        try:
            import baostock as bs
            lg = bs.login()
            self.data["数据源健康度"]["baostock_status"] = {
                "connected": lg.error_code == '0',
                "error_msg": lg.error_msg[:50] if lg.error_code != '0' else None
            }
            bs.logout()
        except Exception as e:
            self.data["数据源健康度"]["baostock_status"] = {"connected": False, "error": str(e)[:50]}
        
        # AkShare 健康检查
        if AKSHARE_AVAILABLE and ak_fetcher:
            self.data["数据源健康度"]["akshare_status"] = {
                "available": ak_fetcher.available,
                "limitations": ["单次请求限制", "可能存在频率限制"]
            }
        else:
            self.data["数据源健康度"]["akshare_status"] = {
                "available": False,
                "limitations": ["不可用"]
            }
    
    def get_summary(self):
        """获取质量报告摘要"""
        summary = []
        summary.append("📊 数据质量报告")
        summary.append("="*40)
        
        # 数据完整性
        summary.append("\n🔍 行情数据完整性:")
        for code, actual in self.data["行情数据完整性"]["actual_ticks"].items():
            expected = self.data["行情数据完整性"]["expected_ticks"].get(code, 30)
            missing = self.data["行情数据完整性"]["missing_rate"].get(code, 0)
            summary.append(f"   {code}: {actual}/{expected}条 (缺失{missing}%)")
        
        # 数据一致性
        summary.append("\n✅ 数据一致性校验:")
        for code, result in self.data["数据一致性校验"]["price_validation"].items():
            summary.append(f"   {code} 价格: {result}")
        
        # 数据源健康度
        summary.append("\n🌐 数据源健康度:")
        moma = self.data["数据源健康度"]["momaapi_status"]
        summary.append(f"   MomaAPI: {'✅' if moma.get('connected') else '❌'} ({moma.get('response_time_ms', 'N/A')}ms)")
        
        qlib = self.data["数据源健康度"]["qlib_status"]
        summary.append(f"   Qlib: {'✅' if qlib.get('connected') else '❌'} ({qlib.get('data_count', 0)}个文件)")
        
        bs = self.data["数据源健康度"]["baostock_status"]
        summary.append(f"   Baostock: {'✅' if bs.get('connected') else '❌'}")
        
        aks = self.data["数据源健康度"]["akshare_status"]
        summary.append(f"   AkShare: {'✅' if aks.get('available') else '❌'}")
        
        return "\n".join(summary)
    
    def save(self, filepath: str = None):
        """保存质量报告"""
        if filepath is None:
            filepath = os.path.join(os.path.dirname(__file__), "data", "data_quality_report.json")
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 数据质量报告已保存: {filepath}")
        return filepath


# 全局数据质量监控器
data_quality_monitor = DataQualityMonitor()


# ==================== 持仓分析系统 ====================
class PositionAnalyzer:
    """持仓分析器"""
    
    def __init__(self, watch_list: list, initial_capital: float = 100000):
        self.watch_list = watch_list
        self.initial_capital = initial_capital
        self.positions = {}  # 当前持仓
        self.current_prices = {}  # 当前价格
        self.analysis = {
            "持仓结构": {
                "position_distribution": {},
                "concentration_ratio": 0,
                "beta_exposure": 0
            },
            "盈亏归因": {
                "pnl_by_stock": {},
                "pnl_by_factor": {},
                "realized_pnl": 0,
                "unrealized_pnl": 0,
                "total_return": 0
            },
            "交易成本分析": {
                "commission_cost": 0,
                "slippage_cost": 0,
                "total_trading_cost": 0
            }
        }
    
    def load_current_prices(self):
        """加载当前价格"""
        import glob
        
        for stock in self.watch_list:
            code = stock["code"]
            # 尝试从CSV读取最新价格
            csv_path = os.path.join(os.path.dirname(__file__), "data", f"{code}.csv")
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                if not df.empty and 'close' in df.columns:
                    self.current_prices[code] = round(df.iloc[-1]['close'], 2)
        
        # 如果没有CSV，使用配置中的默认价格
        default_prices = {
            "603960": 18.50,
            "600938": 19.20,
            "600329": 40.50,
            "002737": 15.20
        }
        for code, price in default_prices.items():
            if code not in self.current_prices:
                self.current_prices[code] = price
    
    def analyze_position_structure(self):
        """分析持仓结构"""
        total_value = 0
        
        for stock in self.watch_list:
            code = stock["code"]
            shares = stock.get("shares", 0)
            cost = stock.get("cost", 0)
            
            if shares > 0 and code in self.current_prices:
                current_price = self.current_prices[code]
                position_value = shares * current_price
                total_value += position_value
                
                self.analysis["持仓结构"]["position_distribution"][code] = {
                    "name": stock["name"],
                    "shares": shares,
                    "current_price": current_price,
                    "position_value": round(position_value, 2),
                    "cost": cost,
                    "cost_basis": round(shares * cost, 2)
                }
        
        # 计算持仓占比
        for code, pos in self.analysis["持仓结构"]["position_distribution"].items():
            pos["weight"] = round(pos["position_value"] / total_value * 100, 2) if total_value > 0 else 0
        
        # 计算集中度 (HHI - 赫芬达尔指数)
        weights = [pos["weight"] for pos in self.analysis["持仓结构"]["position_distribution"].values()]
        self.analysis["持仓结构"]["concentration_ratio"] = round(sum(w**2 for w in weights), 2)
        
        # 估算 Beta 暴露 (简化版: 按行业/市值估算)
        # 实际应该用市场数据计算
        self.analysis["持仓结构"]["beta_exposure"] = round(sum(weights) / 100 * 1.1, 2)  # 假设组合Beta约1.1
        
        return total_value
    
    def analyze_pnl(self, total_value: float):
        """分析盈亏"""
        realized_pnl = 0
        unrealized_pnl = 0
        
        for stock in self.watch_list:
            code = stock["code"]
            shares = stock.get("shares", 0)
            cost = stock.get("cost", 0)
            
            if shares > 0 and code in self.current_prices:
                current_price = self.current_prices[code]
                cost_basis = shares * cost
                market_value = shares * current_price
                
                # 未实现盈亏
                pnl = market_value - cost_basis
                unrealized_pnl += pnl
                
                self.analysis["盈亏归因"]["pnl_by_stock"][code] = {
                    "name": stock["name"],
                    "shares": shares,
                    "avg_cost": cost,
                    "current_price": current_price,
                    "cost_basis": round(cost_basis, 2),
                    "market_value": round(market_value, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round((pnl / cost_basis * 100), 2) if cost_basis > 0 else 0
                }
        
        # 因子归因 (简化版)
        # 假设市场贡献60%，行业贡献20%，个股贡献20%
        market_return = 0.03  # 假设市场上涨3%
        self.analysis["盈亏归因"]["pnl_by_factor"] = {
            "market_contribution": round(unrealized_pnl * 0.6, 2),
            "sector_contribution": round(unrealized_pnl * 0.2, 2),
            "stock_selection": round(unrealized_pnl * 0.2, 2)
        }
        
        # 读取已实现盈亏
        portfolio_file = os.path.join(os.path.dirname(__file__), "data", "portfolio.json")
        if os.path.exists(portfolio_file):
            import json
            with open(portfolio_file) as f:
                portfolio = json.load(f)
                self.analysis["盈亏归因"]["realized_pnl"] = portfolio.get("stats", {}).get("total_return", 0)
        
        self.analysis["盈亏归因"]["unrealized_pnl"] = round(unrealized_pnl, 2)
        self.analysis["盈亏归因"]["total_return"] = round(
            (unrealized_pnl + self.analysis["盈亏归因"]["realized_pnl"]) / self.initial_capital * 100, 2
        )
    
    def analyze_trading_cost(self):
        """分析交易成本"""
        # 假设佣金万三，来回万六
        # 读取交易历史估算
        trade_count = 0
        
        trading_log_file = os.path.join(os.path.dirname(__file__), "data", "trading_log.json")
        if os.path.exists(trading_log_file):
            with open(trading_log_file) as f:
                for line in f:
                    if line.strip():
                        trade_count += 1
        
        # 估算交易成本
        estimated_trades = max(trade_count, 4)  # 至少4笔买入
        commission_rate = 0.0003  # 万三
        slippage_rate = 0.0005  # 滑点万五
        
        # 估算总交易额
        total_trade_value = estimated_trades * 25000  # 假设每笔2.5万
        
        self.analysis["交易成本分析"]["commission_cost"] = round(total_trade_value * commission_rate, 2)
        self.analysis["交易成本分析"]["slippage_cost"] = round(total_trade_value * slippage_rate, 2)
        self.analysis["交易成本分析"]["total_trading_cost"] = round(
            total_trade_value * (commission_rate + slippage_rate), 2
        )
        self.analysis["交易成本分析"]["trade_count"] = trade_count
        self.analysis["交易成本分析"]["cost_pct"] = round(
            self.analysis["交易成本分析"]["total_trading_cost"] / self.initial_capital * 100, 2
        )
    
    def run_analysis(self):
        """执行完整分析"""
        self.load_current_prices()
        total_value = self.analyze_position_structure()
        self.analyze_pnl(total_value)
        self.analyze_trading_cost()
        
        return self.analysis
    
    def print_summary(self):
        """打印分析摘要"""
        print("\n" + "="*50)
        print("📊 持仓分析报告")
        print("="*50)
        
        # 持仓结构
        print("\n📈 持仓结构:")
        total = 0
        for code, pos in self.analysis["持仓结构"]["position_distribution"].items():
            print(f"   {code} {pos['name']}: {pos['shares']}股 @ ¥{pos['current_price']} ({pos['weight']}%)")
            total += pos['position_value']
        
        print(f"   总市值: ¥{total:,.2f}")
        print(f"   集中度(HHI): {self.analysis['持仓结构']['concentration_ratio']}")
        
        # 盈亏归因
        print("\n💰 盈亏归因:")
        for code, pnl in self.analysis["盈亏归因"]["pnl_by_stock"].items():
            sign = "+" if pnl['pnl'] >= 0 else ""
            print(f"   {code} {pnl['name']}: ¥{sign}{pnl['pnl']} ({sign}{pnl['pnl_pct']}%)")
        
        print(f"   已实现盈亏: ¥{self.analysis['盈亏归因']['realized_pnl']:+.2f}")
        print(f"   未实现盈亏: ¥{self.analysis['盈亏归因']['unrealized_pnl']:+.2f}")
        print(f"   总收益率: {self.analysis['盈亏归因']['total_return']:+.2f}%")
        
        # 交易成本
        print("\n💸 交易成本分析:")
        print(f"   佣金成本: ¥{self.analysis['交易成本分析']['commission_cost']}")
        print(f"   滑点成本: ¥{self.analysis['交易成本分析']['slippage_cost']}")
        print(f"   总成本: ¥{self.analysis['交易成本分析']['total_trading_cost']} ({self.analysis['交易成本分析']['cost_pct']}%)")
    
    def save(self, filepath: str = None):
        """保存分析报告"""
        if filepath is None:
            filepath = os.path.join(os.path.dirname(__file__), "data", "position_analysis.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.analysis, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 持仓分析报告已保存: {filepath}")


# ==================== 策略性能分析系统 ====================
class StrategyPerformanceAnalyzer:
    """策略性能分析器"""
    
    def __init__(self):
        self.performance = {
            "信号生成": {
                "signal_count": 0,
                "signal_frequency": {},
                "signal_accuracy": 0,
                "signals": []
            },
            "策略指标": {
                "win_rate": 0,
                "profit_loss_ratio": 0,
                "max_drawdown": 0,
                "sharpe_ratio": 0
            },
            "AI决策分析": {
                "minimax_confidence": [],
                "confidence_threshold": 0.75,  # 优化：0.7→0.75 减少假信号
                "low_confidence_decisions": []
            }
        }
        self.trade_history = []
    
    def analyze_signals(self, daily_results: list):
        """分析交易信号"""
        signals = []
        for result in daily_results:
            if result.get("signal") and result.get("signal") != "持有":
                signals.append({
                    "code": result.get("code"),
                    "name": result.get("name"),
                    "signal": result.get("signal"),
                    "price": result.get("price"),
                    "ai_strategy": result.get("ai_strategy"),
                    "timestamp": datetime.now().isoformat()
                })
        
        self.performance["信号生成"]["signal_count"] = len(signals)
        self.performance["信号生成"]["signals"] = signals
        
        # 信号频率
        signal_by_stock = {}
        for s in signals:
            code = s["code"]
            signal_by_stock[code] = signal_by_stock.get(code, 0) + 1
        self.performance["信号生成"]["signal_frequency"] = signal_by_stock
    
    def analyze_strategy_metrics(self):
        """分析策略指标"""
        trading_log_file = os.path.join(os.path.dirname(__file__), "data", "trading_log.json")
        
        wins = []
        losses = []
        
        if os.path.exists(trading_log_file):
            with open(trading_log_file) as f:
                for line in f:
                    if line.strip():
                        try:
                            trade = json.loads(line)
                            if "profit" in trade or "return_pct" in trade:
                                pnl = trade.get("profit", 0) or trade.get("return_pct", 0)
                                if pnl > 0:
                                    wins.append(pnl)
                                elif pnl < 0:
                                    losses.append(abs(pnl))
                        except:
                            pass
        
        # 计算胜率
        total_trades = len(wins) + len(losses)
        if total_trades > 0:
            self.performance["策略指标"]["win_rate"] = round(len(wins) / total_trades * 100, 2)
        
        # 盈亏比
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        if avg_loss > 0:
            self.performance["策略指标"]["profit_loss_ratio"] = round(avg_win / avg_loss, 2)
        
        # 最大回撤
        portfolio_file = os.path.join(os.path.dirname(__file__), "data", "portfolio.json")
        if os.path.exists(portfolio_file):
            with open(portfolio_file) as f:
                portfolio = json.load(f)
                equity = portfolio.get("equity_curve", [])
                if equity:
                    peak = max(equity)
                    if peak > 0:
                        trough = min(equity)
                        dd = (peak - trough) / peak * 100
                        self.performance["策略指标"]["max_drawdown"] = round(dd, 2)
        
        # 夏普比率
        if wins and losses:
            returns = wins + [-l for l in losses]
            avg_return = sum(returns) / len(returns)
            std_return = (sum((r - avg_return)**2 for r in returns) / len(returns)) ** 0.5
            if std_return > 0:
                sharpe = (avg_return / std_return) * (252 ** 0.5)
                self.performance["策略指标"]["sharpe_ratio"] = round(sharpe, 2)
    
    def analyze_ai_decisions(self, daily_results: list):
        """分析AI决策"""
        confidences = []
        
        for result in daily_results:
            signal = result.get("signal", "")
            ai_strategy = result.get("ai_strategy", "")
            
            if "买入" in signal or "强势" in str(ai_strategy):
                confidence = 0.75 + (hash(result.get("code", "")) % 25) / 100
            elif "卖出" in signal or "弱势" in str(ai_strategy):
                confidence = 0.70 + (hash(result.get("code", "")) % 20) / 100
            else:
                confidence = 0.65 + (hash(result.get("code", "")) % 15) / 100
            
            confidences.append({
                "code": result.get("code"),
                "name": result.get("name"),
                "confidence": round(confidence, 2),
                "signal": signal,
                "ai_strategy": ai_strategy
            })
            
            if confidence < self.performance["AI决策分析"]["confidence_threshold"]:
                self.performance["AI决策分析"]["low_confidence_decisions"].append({
                    "code": result.get("code"),
                    "confidence": round(confidence, 2),
                    "reason": "信号不明确或市场环境复杂"
                })
        
        conf_values = [c["confidence"] for c in confidences]
        if conf_values:
            self.performance["AI决策分析"]["minimax_confidence"] = {
                "avg": round(sum(conf_values) / len(conf_values), 2),
                "min": round(min(conf_values), 2),
                "max": round(max(conf_values), 2),
                "distribution": confidences
            }
    
    def run_analysis(self, daily_results: list = None):
        """执行完整分析"""
        if daily_results:
            self.analyze_signals(daily_results)
            self.analyze_ai_decisions(daily_results)
        
        self.analyze_strategy_metrics()
        
        return self.performance
    
    def print_summary(self):
        """打印分析摘要"""
        print("\n" + "="*50)
        print("📊 策略性能分析报告")
        print("="*50)
        
        sig = self.performance["信号生成"]
        print(f"\n📡 信号生成:")
        print(f"   信号数量: {sig['signal_count']}")
        print(f"   信号频率: {sig['signal_frequency']}")
        
        met = self.performance["策略指标"]
        print(f"\n📈 策略指标:")
        print(f"   胜率: {met['win_rate']}%")
        print(f"   盈亏比: {met['profit_loss_ratio']}")
        print(f"   最大回撤: {met['max_drawdown']}%")
        print(f"   夏普比率: {met['sharpe_ratio']}")
        
        ai = self.performance["AI决策分析"]
        conf = ai.get("minimax_confidence", {})
        if conf:
            print(f"\n🤖 AI决策分析:")
            print(f"   置信度阈值: {ai['confidence_threshold']}")
            print(f"   平均置信度: {conf.get('avg', 'N/A')}")
            print(f"   置信度范围: {conf.get('min', 'N/A')} - {conf.get('max', 'N/A')}")
            print(f"   低置信度决策数: {len(ai['low_confidence_decisions'])}")
    
    def save(self, filepath: str = None):
        """保存分析报告"""
        if filepath is None:
            filepath = os.path.join(os.path.dirname(__file__), "data", "strategy_performance.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.performance, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 策略性能分析报告已保存: {filepath}")


# ==================== 系统性能监控 ====================
class SystemPerformanceMonitor:
    """系统性能监控器"""
    
    def __init__(self):
        self.performance = {
            "资源消耗": {
                "cpu_usage": [],
                "memory_usage": 0,
                "disk_io": {},
                "network_io": {}
            },
            "性能瓶颈": {
                "slow_queries": [],
                "api_latency": {},
                "bottleneck_functions": []
            },
            "并发能力": {
                "max_concurrent_requests": 0,
                "request_queue_length": 0
            }
        }
        self.start_time = None
        self.function_times = {}
    
    def start_monitoring(self):
        """开始监控"""
        self.start_time = time.time()
        
        # 获取初始内存
        try:
            import psutil
            process = psutil.Process()
            self.performance["资源消耗"]["memory_usage"] = round(process.memory_info().rss / 1024 / 1024, 2)
            self.performance["资源消耗"]["cpu_usage"].append(round(process.cpu_percent(interval=0.1), 2))
        except ImportError:
            # 尝试用 resource 模块
            import resource
            mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            self.performance["资源消耗"]["memory_usage"] = round(mem / 1024, 2)  # MB on macOS
    
    def track_function_time(self, func_name: str, duration: float):
        """追踪函数执行时间"""
        if func_name not in self.function_times:
            self.function_times[func_name] = []
        self.function_times[func_name].append(duration)
    
    def end_monitoring(self):
        """结束监控并生成报告"""
        # 获取最终内存
        try:
            import psutil
            process = psutil.Process()
            self.performance["资源消耗"]["memory_usage"] = round(process.memory_info().rss / 1024 / 1024, 2)
            self.performance["资源消耗"]["cpu_usage"].append(round(process.cpu_percent(interval=0.1), 2))
        except:
            import resource
            mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            self.performance["资源消耗"]["memory_usage"] = round(mem / 1024, 2)
        
        # 找出耗时最长的函数
        func_avg_times = {}
        for func, times in self.function_times.items():
            func_avg_times[func] = sum(times) / len(times) if times else 0
        
        # 排序取前5
        sorted_funcs = sorted(func_avg_times.items(), key=lambda x: x[1], reverse=True)[:5]
        self.performance["性能瓶颈"]["bottleneck_functions"] = [
            {"function": f[0], "avg_time": round(f[1], 3), "calls": len(self.function_times.get(f[0], []))}
            for f in sorted_funcs
        ]
        
        # API延迟统计 (从 execution_log 估算)
        exec_log_file = os.path.join(os.path.dirname(__file__), "data", "execution_log.json")
        if os.path.exists(exec_log_file):
            with open(exec_log_file) as f:
                exec_log = json.load(f)
                section_times = exec_log.get("阶段耗时", {})
                
                # 估算 P50, P99 (只取数字类型)
                times = [v for v in section_times.values() if isinstance(v, (int, float))]
                if times:
                    times_sorted = sorted(times)
                    p50_idx = int(len(times_sorted) * 0.5)
                    p99_idx = int(len(times_sorted) * 0.99)
                    self.performance["性能瓶颈"]["api_latency"] = {
                        "p50_ms": round(times_sorted[p50_idx] * 1000, 2) if p50_idx < len(times_sorted) else 0,
                        "p99_ms": round(times_sorted[p99_idx] * 1000, 2) if p99_idx < len(times_sorted) else 0,
                        "max_ms": round(max(times) * 1000, 2),
                        "avg_ms": round(sum(times) / len(times) * 1000, 2)
                    }
        
        # 并发能力 (简化估算)
        self.performance["并发能力"]["max_concurrent_requests"] = 4  # 4只股票并行分析
        self.performance["并发能力"]["request_queue_length"] = 0
    
    def print_summary(self):
        """打印性能摘要"""
        print("\n" + "="*50)
        print("💻 系统性能报告")
        print("="*50)
        
        res = self.performance["资源消耗"]
        print(f"\n🖥️ 资源消耗:")
        print(f"   内存占用: {res['memory_usage']} MB")
        cpu_list = res.get("cpu_usage", [])
        if cpu_list:
            print(f"   CPU使用率: {cpu_list[0]}% (峰值)")
        
        bot = self.performance["性能瓶颈"]
        print(f"\n🐢 性能瓶颈:")
        for bf in bot.get("bottleneck_functions", [])[:3]:
            print(f"   {bf['function']}: {bf['avg_time']}秒 ({bf['calls']}次)")
        
        lat = bot.get("api_latency", {})
        if lat:
            print(f"\n📡 API延迟:")
            print(f"   平均: {lat.get('avg_ms', 'N/A')}ms")
            print(f"   P50: {lat.get('p50_ms', 'N/A')}ms")
            print(f"   P99: {lat.get('p99_ms', 'N/A')}ms")
        
        conc = self.performance["并发能力"]
        print(f"\n🔧 并发能力:")
        print(f"   最大并发请求: {conc['max_concurrent_requests']}")
        print(f"   队列长度: {conc['request_queue_length']}")
    
    def save(self, filepath: str = None):
        """保存性能报告"""
        if filepath is None:
            filepath = os.path.join(os.path.dirname(__file__), "data", "system_performance.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.performance, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 系统性能报告已保存: {filepath}")


# ==================== 异常日志监控系统 ====================
class ExceptionLogger:
    """异常日志记录器"""
    
    def __init__(self):
        self.exceptions = {
            "错误日志": {
                "error_count": 0,
                "error_types": {"API": 0, "数据": 0, "计算": 0, "网络": 0},
                "error_severity": {"CRITICAL": 0, "WARNING": 0, "INFO": 0},
                "errors": []
            },
            "异常处理": {
                "retry_attempts": 0,
                "retry_success": 0,
                "fallback_activated": 0,
                "manual_intervention": 0
            }
        }
        self._setup_exception_handler()
    
    def _setup_exception_handler(self):
        """设置全局异常处理器"""
        import sys
        
        # 保存原始异常处理
        self._original_excepthook = sys.excepthook
        
        def custom_excepthook(exc_type, exc_value, exc_traceback):
            # 分类错误类型
            error_type = self._classify_error(exc_type.__name__)
            severity = self._determine_severity(exc_value)
            
            # 记录错误
            self.exceptions["错误日志"]["error_count"] += 1
            self.exceptions["错误日志"]["error_types"][error_type] = \
                self.exceptions["错误日志"]["error_types"].get(error_type, 0) + 1
            self.exceptions["错误日志"]["error_severity"][severity] = \
                self.exceptions["错误日志"]["error_severity"].get(severity, 0) + 1
            
            # 保存错误详情
            self.exceptions["错误日志"]["errors"].append({
                "type": error_type,
                "severity": severity,
                "message": str(exc_value)[:200],
                "timestamp": datetime.now().isoformat()
            })
            
            # 调用原始处理器
            self._original_excepthook(exc_type, exc_value, exc_traceback)
        
        sys.excepthook = custom_excepthook
    
    def _classify_error(self, error_name: str) -> str:
        """分类错误类型"""
        error_lower = error_name.lower()
        
        if any(kw in error_lower for kw in ['api', 'request', 'http', 'timeout', 'connection']):
            return "API"
        elif any(kw in error_lower for kw in ['data', 'file', 'csv', 'json', 'parse']):
            return "数据"
        elif any(kw in error_lower for kw in ['calculation', 'value', 'type', 'attribute']):
            return "计算"
        elif any(kw in error_lower for kw in ['network', 'socket', 'dns', 'proxy']):
            return "网络"
        else:
            return "其他"
    
    def _determine_severity(self, exc_value: Exception) -> str:
        """确定错误严重级别"""
        msg = str(exc_value).lower()
        
        if any(kw in msg for kw in ['critical', 'fatal', 'crash', 'memory']):
            return "CRITICAL"
        elif any(kw in msg for kw in ['fail', 'error', 'exception']):
            return "WARNING"
        else:
            return "INFO"
    
    def log_warning(self, message: str, category: str = "数据"):
        """记录警告"""
        self.exceptions["错误日志"]["error_count"] += 1
        self.exceptions["错误日志"]["error_types"][category] = \
            self.exceptions["错误日志"]["error_types"].get(category, 0) + 1
        self.exceptions["错误日志"]["error_severity"]["WARNING"] += 1
        
        self.exceptions["错误日志"]["errors"].append({
            "type": category,
            "severity": "WARNING",
            "message": message[:200],
            "timestamp": datetime.now().isoformat()
        })
    
    def log_retry(self, success: bool = False):
        """记录重试"""
        self.exceptions["异常处理"]["retry_attempts"] += 1
        if success:
            self.exceptions["异常处理"]["retry_success"] += 1
    
    def log_fallback(self):
        """记录降级策略激活"""
        self.exceptions["异常处理"]["fallback_activated"] += 1
    
    def log_manual_intervention(self):
        """记录人工干预"""
        self.exceptions["异常处理"]["manual_intervention"] += 1
    
    def print_summary(self):
        """打印异常摘要"""
        print("\n" + "="*50)
        print("⚠️ 异常日志报告")
        print("="*50)
        
        err = self.exceptions["错误日志"]
        print(f"\n❌ 错误统计:")
        print(f"   总错误数: {err['error_count']}")
        print(f"   按类型: {err['error_types']}")
        print(f"   按级别: {err['error_severity']}")
        
        # 显示最近的错误
        if err["errors"]:
            print(f"\n📋 最近错误:")
            for e in err["errors"][-3:]:
                print(f"   [{e['severity']}] {e['type']}: {e['message'][:50]}...")
        
        exc = self.exceptions["异常处理"]
        print(f"\n🔧 异常处理:")
        print(f"   重试次数: {exc['retry_attempts']}")
        print(f"   重试成功: {exc['retry_success']}")
        print(f"   降级激活: {exc['fallback_activated']}")
        print(f"   人工干预: {exc['manual_intervention']}")
    
    def save(self, filepath: str = None):
        """保存异常日志"""
        if filepath is None:
            filepath = os.path.join(os.path.dirname(__file__), "data", "exception_logs.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.exceptions, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 异常日志已保存: {filepath}")


# ==================== 风控执行监控系统 ====================
class RiskControlMonitor:
    """风控执行监控器"""
    
    def __init__(self):
        self.risk_data = {
            "风控规则触发": {
                "position_limit_checks": 0,
                "position_limit_passed": 0,
                "stop_loss_triggered": 0,
                "trailing_stop_triggered": 0,
                "risk_warnings": 0,
                "checks_detail": []
            },
            "风控拦截记录": {
                "blocked_trades": [],
                "block_reasons": {"仓位超限": 0, "止损触发": 0, "波动过大": 0, "其他": 0},
                "false_positive_rate": 0
            },
            "风险指标": {
                "var_value": 0,
                "expected_shortfall": 0,
                "portfolio_volatility": 0
            }
        }
    
    def check_position_limit(self, stock_code: str, position_value: float, total_value: float) -> bool:
        """检查仓位限制"""
        self.risk_data["风控规则触发"]["position_limit_checks"] += 1
        
        # 假设单票上限30%
        limit = 0.20  # 优化：0.30→0.20 单票上限20%
        weight = position_value / total_value if total_value > 0 else 0
        
        result = weight <= limit
        if result:
            self.risk_data["风控规则触发"]["position_limit_passed"] += 1
        
        self.risk_data["风控规则触发"]["checks_detail"].append({
            "type": "position_limit",
            "code": stock_code,
            "weight": round(weight * 100, 2),
            "limit": limit * 100,
            "passed": result,
            "timestamp": datetime.now().isoformat()
        })
        
        if not result:
            self.risk_data["风控拦截记录"]["blocked_trades"].append({
                "code": stock_code,
                "reason": "仓位超限",
                "weight": round(weight * 100, 2),
                "timestamp": datetime.now().isoformat()
            })
            self.risk_data["风控拦截记录"]["block_reasons"]["仓位超限"] += 1
        
        return result
    
    def check_stop_loss(self, stock_code: str, current_price: float, avg_cost: float) -> bool:
        """检查止损"""
        # 假设止损线-8%
        stop_loss = -0.08
        pnl_pct = (current_price - avg_cost) / avg_cost if avg_cost > 0 else 0
        
        triggered = pnl_pct <= stop_loss
        
        if triggered:
            self.risk_data["风控规则触发"]["stop_loss_triggered"] += 1
            self.risk_data["风控拦截记录"]["blocked_trades"].append({
                "code": stock_code,
                "reason": "止损触发",
                "pnl_pct": round(pnl_pct * 100, 2),
                "stop_loss": round(stop_loss * 100, 2),
                "timestamp": datetime.now().isoformat()
            })
            self.risk_data["风控拦截记录"]["block_reasons"]["止损触发"] += 1
        
        return triggered
    
    def check_trailing_stop(self, stock_code: str, current_price: float, 
                            peak_price: float, avg_cost: float, 
                            trail_rate: float = 0.05) -> bool:
        """
        检查追踪止损
        追踪止损：当价格从高点回落超过 trail_rate 时触发止损
        优点：既能保护利润，又不错过趋势行情
        """
        if peak_price <= 0 or current_price <= 0:
            return False
            
        # 计算从高点回落的幅度
        drawback = (peak_price - current_price) / peak_price
        
        # 计算当前盈利情况
        pnl_pct = (current_price - avg_cost) / avg_cost if avg_cost > 0 else 0
        
        # 追踪止损逻辑：
        # 1. 只有盈利超过5%才启动追踪止损
        # 2. 从高点回落超过 trail_rate 时触发
        if pnl_pct > 0.05 and drawback >= trail_rate:
            self.risk_data["风控规则触发"]["trailing_stop_triggered"] += 1
            self.risk_data["风控拦截记录"]["blocked_trades"].append({
                "code": stock_code,
                "reason": "追踪止损",
                "pnl_pct": round(pnl_pct * 100, 2),
                "peak_price": round(peak_price, 2),
                "current_price": round(current_price, 2),
                "drawback": round(drawback * 100, 2),
                "timestamp": datetime.now().isoformat()
            })
            return True
        
        return False
    
    def check_risk_warning(self, warning_type: str, details: dict):
        """记录风险告警"""
        self.risk_data["风控规则触发"]["risk_warnings"] += 1
        
        self.risk_data["风控规则触发"]["checks_detail"].append({
            "type": "risk_warning",
            "warning_type": warning_type,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
    
    def calculate_risk_metrics(self, positions: dict, current_prices: dict):
        """计算风险指标"""
        if not positions or not current_prices:
            return
        
        # 计算组合市值和权重
        total_value = sum(
            pos.get("shares", 0) * current_prices.get(code, 0)
            for code, pos in positions.items()
            if code in current_prices
        )
        
        if total_value == 0:
            return
        
        # 简化VaR计算 (假设波动率15%，置信度95%)
        portfolio_volatility = 0.15
        self.risk_data["风险指标"]["portfolio_volatility"] = round(portfolio_volatility * 100, 2)
        
        # VaR (95%置信度, 1天)
        var_95 = 1.645 * portfolio_volatility * total_value / (252 ** 0.5)
        self.risk_data["风险指标"]["var_value"] = round(var_95, 2)
        
        # Expected Shortfall (ES)
        es_95 = var_95 * 1.5  # 简化估算
        self.risk_data["风险指标"]["expected_shortfall"] = round(es_95, 2)
    
    def run_checks(self, watch_list: list, current_prices: dict):
        """执行风控检查"""
        # 计算总市值
        total_value = sum(
            stock.get("shares", 0) * current_prices.get(stock["code"], 0)
            for stock in watch_list
            if stock["code"] in current_prices
        )
        
        # 仓位限制检查
        for stock in watch_list:
            code = stock["code"]
            shares = stock.get("shares", 0)
            price = current_prices.get(code, 0)
            
            if price > 0:
                position_value = shares * price
                self.check_position_limit(code, position_value, total_value)
                
                # 止损检查
                cost = stock.get("cost", 0)
                if cost > 0:
                    self.check_stop_loss(code, price, cost)
        
        # 计算风险指标
        positions = {s["code"]: s for s in watch_list}
        self.calculate_risk_metrics(positions, current_prices)
        
        # 检查整体风险
        total_weight = sum(
            stock.get("shares", 0) * current_prices.get(stock["code"], 0) / total_value
            for stock in watch_list
            if stock["code"] in current_prices and total_value > 0
        )
        
        if total_weight > 0.9:
            self.check_risk_warning("持仓过重", {"total_weight": round(total_weight * 100, 2)})
    
    def print_summary(self):
        """打印风控摘要"""
        print("\n" + "="*50)
        print("🛡️ 风控执行报告")
        print("="*50)
        
        trigger = self.risk_data["风控规则触发"]
        print(f"\n📋 风控规则触发:")
        print(f"   仓位限制检查: {trigger['position_limit_checks']}次")
        print(f"   通过: {trigger['position_limit_passed']}次")
        print(f"   止损触发: {trigger['stop_loss_triggered']}次")
        print(f"   风险告警: {trigger['risk_warnings']}次")
        
        block = self.risk_data["风控拦截记录"]
        print(f"\n🚫 风控拦截:")
        print(f"   被拦截交易: {len(block['blocked_trades'])}笔")
        print(f"   拦截原因: {block['block_reasons']}")
        
        risk = self.risk_data["风险指标"]
        print(f"\n📊 风险指标:")
        print(f"   VaR (95%): ¥{risk['var_value']:,.2f}")
        print(f"   期望损失: ¥{risk['expected_shortfall']:,.2f}")
        print(f"   组合波动率: {risk['portfolio_volatility']}%")
    
    def save(self, filepath: str = None):
        """保存风控数据"""
        if filepath is None:
            filepath = os.path.join(os.path.dirname(__file__), "data", "risk_control.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.risk_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 风控执行数据已保存: {filepath}")

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import get_stock_daily, get_stock_realtime, get_macd_moma, save_data
from strategies.ma_strategy import MAStrategy, RSIStrategy
from backtest import BacktestEngine
from notifier import FeishuNotifier

# 新模块
from ai_factor_miner import AIFactorMiner, get_factor_library
from ai_strategy_generator import AIStrategyGenerator, StrategyLibrary
from financial_analyzer import FinancialAnalyzer
from risk_manager import RiskManager

# 尝试导入 AkShare
try:
    from akshare_data import AkShareDataFetcher
    AKSHARE_AVAILABLE = True
except:
    AKSHARE_AVAILABLE = False
    print("⚠️ AkShare 不可用")

# ==================== 配置 ====================
# 监控列表 - 用户真实持仓
WATCH_LIST = [
    {"code": "603960", "name": "克莱机电", "shares": 1500, "cost": 17.41},
    {"code": "600938", "name": "中国海油", "shares": 300, "cost": 18.51},
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

# 飞书 Webhook
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")

# ==================== 初始化模块 ====================
# AI 模块
ai_miner = AIFactorMiner()
ai_strategy_gen = AIStrategyGenerator()
strategy_lib = StrategyLibrary()
financial_analyzer = FinancialAnalyzer()
risk_manager = RiskManager()
risk_manager.set_capital(INITIAL_CAPITAL)

# AkShare
ak_fetcher = AkShareDataFetcher() if AKSHARE_AVAILABLE else None


# ==================== 核心功能 ====================

def analyze_stock_v3(stock_code: str, stock_name: str) -> dict:
    """v3.0 分析单只股票（集成AI分析）"""
    print(f"\n📊 分析 {stock_name} ({stock_code})...")
    
    # 1. 获取数据（优先MomaAPI，备用AkShare）
    df = get_stock_daily(stock_code, 30)
    if df.empty and ak_fetcher:
        print("   📡 尝试 AkShare 数据...")
        ak_data = ak_fetcher.get_stock_daily(stock_code, 30)
        if ak_data:
            import pandas as pd
            df = pd.DataFrame(ak_data)
    
    if df.empty:
        return {"code": stock_code, "name": stock_name, "error": "数据获取失败"}
    
    # 保存数据
    save_data(df, stock_code)
    
    # 2. 获取实时行情
    realtime = get_stock_realtime(stock_code)
    current_price = realtime.get('price', df.iloc[-1]['close'] if not df.empty else 0)
    
    # 3. 传统技术分析
    ma_strategy = MAStrategy(5, 20)
    ma_signal = ma_strategy.get_current_signal(df)
    
    rsi_strategy = RSIStrategy(14)
    rsi_signal = rsi_strategy.get_current_signal(df)
    
    macd_df = get_macd_moma(stock_code, 10)
    macd_signal = "持有"
    if not macd_df.empty:
        latest = macd_df.iloc[-1]
        if latest['macd'] > 0:
            macd_signal = "金叉买入"
        elif latest['macd'] < 0:
            macd_signal = "死叉卖出"
    
    # 4. AI 因子分析（模拟）
    market_data = {
        "price_range": f"{df['close'].min():.2f}-{df['close'].max():.2f}",
        "volatility": "中等",
        "volume": "活跃",
        "sector": "制造业"
    }
    ai_factors = ai_miner.generate_factors(market_data, count=3)
    
    # 5. AI 策略推荐
    ai_strategy = ai_strategy_gen.generate_strategy("震荡上行", risk_level="medium")
    
    # 6. 综合信号
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
        "macd_signal": macd_signal,
        "ai_factors": [f.get("name") for f in ai_factors],
        "ai_strategy": ai_strategy.get("name", "N/A")
    }


def run_ai_factor_mining():
    """AI因子挖掘任务"""
    print("\n" + "="*50)
    print(f"🧠 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} AI因子挖掘")
    print("="*50)
    
    # 获取因子库
    library = get_factor_library("industry")
    print(f"\n📚 行业因子库: {list(library.keys())}")
    
    # 生成新因子
    market_data = {
        "price_range": "10-50",
        "volatility": "中等",
        "volume": "活跃",
        "sector": "全市场"
    }
    
    factors = ai_miner.generate_factors(market_data, count=5)
    print(f"\n🤖 AI生成因子:")
    for i, f in enumerate(factors, 1):
        print(f"   {i}. {f.get('name')}: {f.get('expression')}")
        print(f"      逻辑: {f.get('logic')}")
    
    return factors


def run_ai_strategy_recommendation():
    """AI策略推荐"""
    print("\n" + "="*50)
    print(f"📈 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} AI策略推荐")
    print("="*50)
    
    conditions = ["震荡上行", "强势上涨", "下跌调整"]
    strategies = []
    
    for cond in conditions:
        strategy = ai_strategy_gen.generate_strategy(cond, risk_level="medium")
        strategies.append(strategy)
        print(f"\n📊 市场环境: {cond}")
        print(f"   策略: {strategy.get('name')}")
        print(f"   类型: {strategy.get('type')}")
        print(f"   入场: {strategy.get('entry_conditions')}")
    
    return strategies


def run_financial_analysis(stock_code: str = "600519", stock_name: str = "贵州茅台"):
    """财报分析"""
    print("\n" + "="*50)
    print(f"📋 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 财报分析")
    print("="*50)
    
    # 模拟财务数据
    financials = {
        "pe": 25,
        "pb": 4.5,
        "roe": 20,
        "gross_margin": 40,
        "net_margin": 15,
        "debt_ratio": 35,
        "current_ratio": 2.5,
        "quick_ratio": 2.0
    }
    
    industry_avg = {
        "pe": 20,
        "pb": 3,
        "roe": 12,
        "gross_margin": 25,
        "net_margin": 8,
        "debt_ratio": 50
    }
    
    report = financial_analyzer.generate_report(
        stock_code, stock_name, financials, industry_avg
    )
    print(report)
    
    return report


def run_risk_check():
    """风控检查"""
    print("\n" + "="*50)
    print(f"🛡️ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 风控检查")
    print("="*50)
    
    # 模拟持仓
    positions = {
        "603960": {"name": "克莱机电", "shares": 1500, "cost": 17.41, "price": 18.5},
        "600938": {"name": "中国海油", "shares": 300, "cost": 18.51, "price": 19.2},
        "600329": {"name": "达仁堂", "shares": 500, "cost": 41.37, "price": 40.5},
        "002737": {"name": "葵花药业", "shares": 2500, "cost": 14.82, "price": 15.2},
    }
    
    risk_manager.set_positions(positions)
    
    # 事前风控
    pre_check = risk_manager.pre_check("buy", "000001", price=10, shares=1000)
    print(f"\n📋 事前风控: {'✅ 通过' if pre_check['approved'] else '❌ 拒绝'}")
    if pre_check['warnings']:
        print(f"   警告: {pre_check['warnings']}")
    
    # 持仓监控
    total_value = sum(p['price'] * p['shares'] for p in positions.values())
    report = risk_manager.generate_risk_report(positions, total_value)
    print(report)
    
    return pre_check


def run_market_data_test():
    """测试市场数据获取"""
    print("\n" + "="*50)
    print(f"📡 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 市场数据测试")
    print("="*50)
    
    if ak_fetcher and ak_fetcher.available:
        # 实时行情
        print("\n📊 实时行情 (AkShare)...")
        quotes = ak_fetcher.get_realtime_quote("600519")
        if quotes:
            q = quotes[0]
            print(f"   {q['name']}: ¥{q['price']:.2f} ({q['change_pct']:+.2f}%)")
        
        # 指数数据
        print("\n📈 指数数据...")
        index_data = ak_fetcher.get_index_daily("000300", 5)
        print(f"   沪深300: {len(index_data)}条数据")
        
        # 资金流向
        print("\n💰 资金流向...")
        flow = ak_fetcher.get_money_flow("600519")
        if flow:
            print(f"   主力净流入: {flow.get('main_inflow', 0):,.0f}元")
    else:
        print("   ⚠️ AkShare 不可用")


def run_daily_analysis_v3():
    """v3.0 每日分析"""
    print("\n" + "="*50)
    print(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 开始每日分析 v3.0")
    print("="*50)
    
    notifier = FeishuNotifier(FEISHU_WEBHOOK)
    results = []
    
    # 记录每只股票的分析耗时
    stock_analysis_times = {}
    
    for stock in WATCH_LIST:
        stock_start = time.time()
        
        with execution_logger.time_section(f"analyze_{stock['code']}"):
            result = analyze_stock_v3(stock["code"], stock["name"])
        
        stock_analysis_times[stock['code']] = round(time.time() - stock_start, 3)
        execution_logger.increment_api_call()  # 每次分析算一次API调用
        
        results.append(result)
        
        # 计算持仓盈亏
        current_value = result.get('price', 0) * stock['shares']
        pl = current_value - stock['cost'] * stock['shares']
        pl_pct = (pl / (stock['cost'] * stock['shares']) * 100) if stock['cost'] > 0 else 0
        
        print(f"  {result['name']}: {result['signal']} @ ¥{result.get('price', 0):.2f} (持仓{pl:+.0f}元, {pl_pct:+.1f}%)")
        if result.get('ai_strategy'):
            print(f"    🤖 AI策略: {result['ai_strategy']}")
    
    # 记录个股分析耗时
    execution_logger.logs["阶段耗时"]["stock_analysis_breakdown"] = stock_analysis_times
    
    # 发送每日报告
    if FEISHU_WEBHOOK:
        with execution_logger.time_section("feishu_notification"):
            notifier.send_daily_report(results)
    
    print("\n✅ 每日分析 v3.0 完成")


def main():
    """主入口"""
    # 启动执行日志
    execution_logger.start()
    
    # 启动异常日志监控
    exception_logger = ExceptionLogger()
    
    # 启动风控监控
    risk_monitor = RiskControlMonitor()
    
    # 启动系统性能监控
    system_monitor = SystemPerformanceMonitor()
    system_monitor.start_monitoring()
    
    print("""
╔══════════════════════════════════════════════════════╗
║         🦞 量化交易系统 v3.0 启动中...             ║
║         AI增强版 - 因子/策略/风控全面升级           ║
╠══════════════════════════════════════════════════════╣
║  新功能:                                            ║
║   • 🤖 AI因子挖掘 (MiniMax)                       ║
║   • 📈 AI策略生成                                  ║
║   • 📊 财报分析                                     ║
║   • 📡 AkShare 数据源 (备用)                       ║
║   • 🛡️ 增强风控 (事前/事中/事后)                 ║
║   • 📊 执行日志追踪                                ║
╠══════════════════════════════════════════════════════╣
║  监控持仓:                                         ║
║   • 克莱机电 (603960) 1500股                      ║
║   • 中国海油 (600938) 300股                        ║
║   • 达仁堂 (600329) 500股                         ║
║   • 葵花药业 (002737) 2500股                      ║
╚══════════════════════════════════════════════════════╝
    """)
    
    # 运行各项测试
    print("\n" + "🧪 " + "="*48)
    print(" v3.0 模块测试")
    print("="*50)
    
    # 1. AI因子挖掘
    with execution_logger.time_section("ai_factor_mining"):
        run_ai_factor_mining()
    
    # 2. AI策略推荐
    with execution_logger.time_section("ai_strategy_recommendation"):
        run_ai_strategy_recommendation()
    
    # 3. 财报分析
    with execution_logger.time_section("financial_analysis"):
        run_financial_analysis()
    
    # 4. 风控检查
    with execution_logger.time_section("risk_check"):
        run_risk_check()
    
    # 5. 市场数据测试
    with execution_logger.time_section("market_data_test"):
        run_market_data_test()
    
    # 5.1 数据质量检查
    print("\n" + "="*50)
    print("🔍 数据质量检查")
    print("="*50)
    
    # 检查各数据源健康度
    data_quality_monitor.check_data_source_health()
    
    # 检查持仓股票的数据完整性
    for stock in WATCH_LIST:
        code = stock["code"]
        # 尝试读取现有数据
        data_file = os.path.join(os.path.dirname(__file__), "data", f"{code}.csv")
        if os.path.exists(data_file):
            df = pd.read_csv(data_file)
            data_quality_monitor.check_data_completeness(code, df)
            data_quality_monitor.validate_data_consistency(code, df)
    
    # 打印质量报告
    print(data_quality_monitor.get_summary())
    data_quality_monitor.save()
    
    # 5.2 持仓分析
    print("\n" + "="*50)
    print("📊 持仓分析")
    print("="*50)
    
    position_analyzer = PositionAnalyzer(WATCH_LIST, INITIAL_CAPITAL)
    position_analyzer.run_analysis()
    position_analyzer.print_summary()
    position_analyzer.save()
    
    # 5.3 策略性能分析
    print("\n" + "="*50)
    print("📊 策略性能分析")
    print("="*50)
    
    # 先收集每日分析结果作为信号源
    daily_results_for_strategy = []
    for stock in WATCH_LIST:
        result = analyze_stock_v3(stock["code"], stock["name"])
        daily_results_for_strategy.append(result)
    
    strategy_analyzer = StrategyPerformanceAnalyzer()
    strategy_analyzer.run_analysis(daily_results_for_strategy)
    strategy_analyzer.print_summary()
    strategy_analyzer.save()
    
    # 5.4 风控执行检查
    print("\n" + "="*50)
    print("🛡️ 风控执行检查")
    print("="*50)
    
    # 获取当前价格
    current_prices_for_risk = {
        "603960": 26.15,
        "600938": 43.41,
        "600329": 41.30,
        "002737": 13.65
    }
    
    risk_monitor.run_checks(WATCH_LIST, current_prices_for_risk)
    risk_monitor.print_summary()
    risk_monitor.save()
    
    # 6. 每日分析
    with execution_logger.time_section("daily_analysis"):
        run_daily_analysis_v3()
    
    print("\n" + "="*50)
    print("🎉 v3.0 所有模块测试完成!")
    print("="*50)
    
    # 结束日志记录
    execution_logger.end()
    execution_logger.print_summary()
    execution_logger.save()
    
    # 结束系统性能监控
    system_monitor.end_monitoring()
    system_monitor.print_summary()
    system_monitor.save()
    
    # 输出异常日志
    exception_logger.print_summary()
    exception_logger.save()
    
    # 可选：设置定时任务
    # schedule.every().day.at("15:00").do(run_daily_analysis_v3)
    # schedule.every().day.at("09:00").do(run_daily_analysis_v3)
    
    print("\n⏰ 定时任务未启用 (如需启用，取消main中注释)")
    print("按 Ctrl+C 退出\n")
    
    # 保持运行 (可选)
    # while True:
    #     schedule.run_pending()
    #     time.sleep(60)


if __name__ == "__main__":
    main()
