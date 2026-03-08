#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化交易系统 - Prometheus 监控指标模块
支持实时监控、可视化、告警
"""
import os
import time
import threading
from datetime import datetime
from prometheus_client import Counter, Gauge, Histogram, Summary, CollectorRegistry, generate_latest, REGISTRY
from http.server import HTTPServer, BaseHTTPRequestHandler
import json


class QuantMetrics:
    """量化交易指标收集器"""
    
    def __init__(self):
        self.registry = REGISTRY
        
        # ==================== 策略指标 ====================
        # 信号计数器
        self.signals_total = Counter(
            'quant_strategy_signals_total',
            'Total strategy signals generated',
            ['strategy', 'side', 'symbol']
        )
        
        # 信号执行计数器
        self.signals_executed = Counter(
            'quant_signals_executed_total',
            'Total signals executed',
            ['strategy', 'result']
        )
        
        # ==================== 持仓指标 ====================
        # 组合价值
        self.portfolio_value = Gauge(
            'quant_portfolio_value',
            'Current portfolio value',
            ['account']
        )
        
        # 持仓权重
        self.position_weight = Gauge(
            'quant_position_weight',
            'Position weight in portfolio',
            ['symbol', 'name']
        )
        
        # 未实现盈亏
        self.unrealized_pnl = Gauge(
            'quant_unrealized_pnl',
            'Unrealized PnL',
            ['symbol']
        )
        
        # ==================== 交易指标 ====================
        # 交易计数器
        self.trades_total = Counter(
            'quant_trades_total',
            'Total trades executed',
            ['side', 'result']
        )
        
        # 交易金额
        self.trade_amount = Histogram(
            'quant_trade_amount',
            'Trade amount',
            ['side'],
            buckets=[1000, 5000, 10000, 50000, 100000, 500000]
        )
        
        # ==================== 风控指标 ====================
        # 风控拦截计数器
        self.risk_blocked = Counter(
            'quant_risk_blocked_total',
            'Total blocked trades by risk control',
            ['reason']
        )
        
        # 风控检查计数器
        self.risk_checks = Counter(
            'quant_risk_checks_total',
            'Total risk control checks',
            ['check_type', 'result']
        )
        
        # VaR 风险价值
        self.var_value = Gauge(
            'quant_var_value',
            'Value at Risk (95%)',
            ['account']
        )
        
        # ==================== 数据指标 ====================
        # 数据获取延迟
        self.data_fetch_latency = Histogram(
            'quant_data_fetch_latency_seconds',
            'Data fetch latency in seconds',
            ['source', 'symbol'],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        )
        
        # 数据质量
        self.data_quality = Gauge(
            'quant_data_quality',
            'Data quality score',
            ['symbol', 'metric']
        )
        
        # ==================== 系统指标 ====================
        # CPU 使用率
        self.cpu_usage = Gauge(
            'quant_system_cpu_usage_percent',
            'CPU usage percent'
        )
        
        # 内存使用
        self.memory_usage = Gauge(
            'quant_system_memory_mb',
            'Memory usage in MB'
        )
        
        # ==================== 性能指标 ====================
        # 执行时间
        self.execution_duration = Histogram(
            'quant_execution_duration_seconds',
            'Execution duration in seconds',
            ['module'],
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
        )
        
        # API 调用延迟
        self.api_latency = Histogram(
            'quant_api_latency_seconds',
            'API call latency',
            ['api_name'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        )
    
    # ==================== 便捷方法 ====================
    
    def record_signal(self, strategy: str, side: str, symbol: str):
        """记录信号"""
        self.signals_total.labels(strategy=strategy, side=side, symbol=symbol).inc()
    
    def record_signal_executed(self, strategy: str, result: str):
        """记录信号执行"""
        self.signals_executed.labels(strategy=strategy, result=result).inc()
    
    def update_portfolio(self, account: str, value: float):
        """更新组合价值"""
        self.portfolio_value.labels(account=account).set(value)
    
    def update_position(self, symbol: str, name: str, weight: float):
        """更新持仓"""
        self.position_weight.labels(symbol=symbol, name=name).set(weight)
    
    def update_unrealized_pnl(self, symbol: str, pnl: float):
        """更新未实现盈亏"""
        self.unrealized_pnl.labels(symbol=symbol).set(pnl)
    
    def record_trade(self, side: str, result: str, amount: float):
        """记录交易"""
        self.trades_total.labels(side=side, result=result).inc()
        self.trade_amount.labels(side=side).observe(amount)
    
    def record_risk_blocked(self, reason: str):
        """记录风控拦截"""
        self.risk_blocked.labels(reason=reason).inc()
    
    def record_risk_check(self, check_type: str, result: str):
        """记录风控检查"""
        self.risk_checks.labels(check_type=check_type, result=result).inc()
    
    def update_var(self, account: str, value: float):
        """更新 VaR"""
        self.var_value.labels(account=account).set(value)
    
    def record_data_fetch(self, source: str, symbol: str, latency: float):
        """记录数据获取"""
        self.data_fetch_latency.labels(source=source, symbol=symbol).observe(latency)
    
    def update_data_quality(self, symbol: str, metric: str, value: float):
        """更新数据质量"""
        self.data_quality.labels(symbol=symbol, metric=metric).set(value)
    
    def update_system_metrics(self, cpu_percent: float, memory_mb: float):
        """更新系统指标"""
        self.cpu_usage.set(cpu_percent)
        self.memory_usage.set(memory_mb)
    
    def record_execution_time(self, module: str, duration: float):
        """记录执行时间"""
        self.execution_duration.labels(module=module).observe(duration)
    
    def record_api_latency(self, api_name: str, latency: float):
        """记录 API 延迟"""
        self.api_latency.labels(api_name=api_name).observe(latency)


# 全局指标实例
quant_metrics = QuantMetrics()


# ==================== 指标服务器 ====================

class MetricsHandler(BaseHTTPRequestHandler):
    """Prometheus 指标 HTTP 处理器"""
    
    def do_GET(self):
        if self.path == '/metrics':
            # 返回 Prometheus 格式的指标
            output = generate_latest(quant_metrics.registry)
            
            self.send_response(200)
            self.send_header('Content-Type', 'output_format')
            self.end_headers()
            self.wfile.write(output)
        
        elif self.path == '/health':
            # 健康检查
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'healthy'}).encode())
        
        elif self.path == '/stats':
            # 自定义统计
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            stats = {
                'timestamp': datetime.now().isoformat(),
                'metrics': {
                    'signals_total': sum(c._value.get() for c in [quant_metrics.signals_total]),
                    'trades_total': sum(c._value.get() for c in [quant_metrics.trades_total]),
                    'risk_blocked': sum(c._value.get() for c in [quant_metrics.risk_blocked]),
                }
            }
            self.wfile.write(json.dumps(stats).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # 抑制日志输出
        pass


def start_metrics_server(port: int = 8000):
    """启动指标服务器"""
    server = HTTPServer(('', port), MetricsHandler)
    print(f"📊 Prometheus 指标服务器已启动: http://localhost:{port}/metrics")
    print(f"   健康检查: http://localhost:{port}/health")
    print(f"   统计信息: http://localhost:{port}/stats")
    
    # 启动服务器线程
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    
    return server


# ==================== 便捷函数 ====================

def record_signal(strategy: str, side: str, symbol: str):
    quant_metrics.record_signal(strategy, side, symbol)

def update_portfolio(account: str, value: float):
    quant_metrics.update_portfolio(account, value)

def update_position(symbol: str, name: str, weight: float):
    quant_metrics.update_position(symbol, name, weight)

def update_unrealized_pnl(symbol: str, pnl: float):
    quant_metrics.update_unrealized_pnl(symbol, pnl)

def record_trade(side: str, result: str, amount: float):
    quant_metrics.record_trade(side, result, amount)

def record_risk_blocked(reason: str):
    quant_metrics.record_risk_blocked(reason)

def record_risk_check(check_type: str, result: str):
    quant_metrics.record_risk_check(check_type, result)

def record_data_fetch(source: str, symbol: str, latency: float):
    quant_metrics.record_data_fetch(source, symbol, latency)

def update_data_quality(symbol: str, metric: str, value: float):
    quant_metrics.update_data_quality(symbol, metric, value)

def record_execution_time(module: str, duration: float):
    quant_metrics.record_execution_time(module, duration)


if __name__ == "__main__":
    # 测试指标
    print("🧪 测试 Prometheus 指标...")
    
    # 模拟数据
    record_signal("AI-网格策略", "buy", "603960")
    record_signal("AI-趋势策略", "sell", "600938")
    
    update_portfolio("main", 107023.0)
    update_position("603960", "克莱机电", 36.65)
    update_unrealized_pnl("603960", 13110.0)
    
    record_trade("buy", "success", 25000.0)
    record_trade("sell", "success", 25000.0)
    
    record_risk_blocked("position_limit")
    record_risk_check("position_limit", "passed")
    
    record_data_fetch("momaapi", "600519", 0.35)
    
    record_execution_time("data_fetch", 2.5)
    
    # 启动服务器
    start_metrics_server(8000)
    
    print("✅ Prometheus 指标测试完成")
    print("📁 访问 http://localhost:8000/metrics 查看指标")
