#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化交易系统 - 结构化日志模块
支持按时间分目录、JSON格式、日志轮转
"""
import os
import sys
import json
import logging
import gzip
from datetime import datetime
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler


class QuantLogger:
    """量化交易日志器"""
    
    def __init__(self, log_root: str = None):
        if log_root is None:
            log_root = os.path.join(os.path.dirname(__file__), "logs")
        
        self.log_root = Path(log_root)
        self.log_root.mkdir(parents=True, exist_ok=True)
        
        # 创建日志器
        self.logger = logging.getLogger('quant_system')
        self.logger.setLevel(logging.DEBUG)
        
        # 避免重复添加handler
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _get_log_path(self, module: str) -> Path:
        """获取日志文件路径 (按日期分目录)"""
        now = datetime.now()
        date_dir = self.log_root / now.strftime('%Y-%m-%d')
        hour_dir = date_dir / now.strftime('%H')
        hour_dir.mkdir(parents=True, exist_ok=True)
        
        return hour_dir / f"{module}.log"
    
    def _setup_handlers(self):
        """设置日志处理器"""
        
        # JSON 格式化器
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": datetime.now().isoformat(),
                    "level": record.levelname,
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                    "message": record.getMessage(),
                }
                
                # 添加异常信息
                if record.exc_info:
                    log_data["exception"] = self.formatException(record.exc_info)
                
                # 添加额外字段
                if hasattr(record, 'extra'):
                    log_data.update(record.extra)
                
                return json.dumps(log_data, ensure_ascii=False)
        
        # 模块配置
        modules = {
            'execution': '执行日志',
            'data_fetch': '数据获取',
            'strategy': '策略执行',
            'risk_control': '风控日志',
            'error': '错误日志',
            'performance': '性能日志',
            'trade': '交易日志'
        }
        
        for module, name in modules.items():
            log_path = self._get_log_path(module)
            
            # 文件处理器 (按小时轮转)
            handler = TimedRotatingFileHandler(
                log_path,
                when='h',  # 按小时
                interval=1,
                backupCount=24 * 7  # 保留7天
            )
            handler.suffix = '%Y%m%d%H%M'  # 文件名后缀
            
            # 设置格式化器
            if module in ['error', 'performance']:
                handler.setFormatter(JSONFormatter())
            else:
                handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                ))
            
            handler.setLevel(logging.DEBUG)
            self.logger.addHandler(handler)
    
    # ==================== 便捷方法 ====================
    
    def log_execution(self, execution_id: str, module: str, duration: float, status: str = "success"):
        """记录执行日志"""
        self.logger.info(f"[{execution_id}] {module} 执行完成, 耗时: {duration:.2f}秒, 状态: {status}", 
                        extra={'extra': {'execution_id': execution_id, 'duration': duration, 'status': status}})
    
    def log_data_fetch(self, source: str, symbol: str, record_count: int, latency: float, success: bool = True):
        """记录数据获取"""
        level = logging.INFO if success else logging.WARNING
        msg = f"数据获取 - 源: {source}, 股票: {symbol}, 记录数: {record_count}, 延迟: {latency:.2f}ms"
        self.logger.log(level, msg, extra={'extra': {
            'source': source, 
            'symbol': symbol, 
            'record_count': record_count, 
            'latency_ms': latency,
            'success': success
        }})
    
    def log_strategy(self, strategy: str, signal: str, symbol: str, price: float, confidence: float):
        """记录策略信号"""
        self.logger.info(f"策略信号 - 策略: {strategy}, 信号: {signal}, 股票: {symbol}, 价格: {price}, 置信度: {confidence:.2f}",
                        extra={'extra': {
                            'strategy': strategy,
                            'signal': signal,
                            'symbol': symbol,
                            'price': price,
                            'confidence': confidence
                        }})
    
    def log_trade(self, action: str, symbol: str, name: str, quantity: int, price: float, pnl: float = 0):
        """记录交易"""
        self.logger.info(f"交易 - 操作: {action}, 股票: {symbol}({name}), 数量: {quantity}, 价格: {price}, 盈亏: {pnl:.2f}",
                        extra={'extra': {
                            'action': action,
                            'symbol': symbol,
                            'name': name,
                            'quantity': quantity,
                            'price': price,
                            'pnl': pnl
                        }})
    
    def log_risk_event(self, event_type: str, severity: str, symbol: str, message: str, details: dict = None):
        """记录风控事件"""
        level = logging.WARNING if severity == 'WARNING' else logging.ERROR if severity == 'CRITICAL' else logging.INFO
        self.logger.log(level, f"风控 - 类型: {event_type}, 级别: {severity}, 股票: {symbol}, 消息: {message}",
                        extra={'extra': {
                            'event_type': event_type,
                            'severity': severity,
                            'symbol': symbol,
                            'message': message,
                            'details': details or {}
                        }})
    
    def log_performance(self, metric_name: str, value: float, unit: str = "", tags: dict = None):
        """记录性能指标"""
        self.logger.debug(f"性能 - 指标: {metric_name}, 值: {value} {unit}",
                         extra={'extra': {
                             'metric_name': metric_name,
                             'value': value,
                             'unit': unit,
                             'tags': tags or {}
                         }})
    
    def log_error(self, error_type: str, message: str, traceback: str = None):
        """记录错误"""
        self.logger.error(f"错误 - 类型: {error_type}, 消息: {message}",
                         extra={'extra': {
                             'error_type': error_type,
                             'message': message,
                             'traceback': traceback
                         }})


# 全局日志器实例
quant_logger = QuantLogger()


# ==================== 便捷函数 ====================

def log_execution(execution_id: str, module: str, duration: float, status: str = "success"):
    """记录执行日志"""
    quant_logger.log_execution(execution_id, module, duration, status)

def log_data_fetch(source: str, symbol: str, record_count: int, latency: float, success: bool = True):
    """记录数据获取"""
    quant_logger.log_data_fetch(source, symbol, record_count, latency, success)

def log_strategy(strategy: str, signal: str, symbol: str, price: float, confidence: float):
    """记录策略信号"""
    quant_logger.log_strategy(strategy, signal, symbol, price, confidence)

def log_trade(action: str, symbol: str, name: str, quantity: int, price: float, pnl: float = 0):
    """记录交易"""
    quant_logger.log_trade(action, symbol, name, quantity, price, pnl)

def log_risk_event(event_type: str, severity: str, symbol: str, message: str, details: dict = None):
    """记录风控事件"""
    quant_logger.log_risk_event(event_type, severity, symbol, message, details)

def log_performance(metric_name: str, value: float, unit: str = "", tags: dict = None):
    """记录性能指标"""
    quant_logger.log_performance(metric_name, value, unit, tags)

def log_error(error_type: str, message: str, traceback: str = None):
    """记录错误"""
    quant_logger.log_error(error_type, message, traceback)


# ==================== 日志归档 ====================

def archive_logs(days_to_keep: int = 7):
    """归档旧日志 (压缩)"""
    if not quant_logger.log_root.exists():
        return
    
    now = datetime.now()
    archived = 0
    
    for date_dir in quant_logger.log_root.iterdir():
        if not date_dir.is_dir():
            continue
        
        # 检查日期
        try:
            dir_date = datetime.strptime(date_dir.name, '%Y-%m-%d')
            age = (now - dir_date).days
            
            if age > days_to_keep:
                # 压缩整个目录
                archive_path = quant_logger.log_root / f"{date_dir.name}.tar.gz"
                
                import tarfile
                with tarfile.open(archive_path, 'w:gz') as tar:
                    tar.add(date_dir, arcname=date_dir.name)
                
                # 删除原目录
                import shutil
                shutil.rmtree(date_dir)
                
                archived += 1
        except ValueError:
            continue
    
    print(f"✅ 已归档 {archived} 个日志目录")


def cleanup_archived(days_to_keep: int = 30):
    """清理归档日志"""
    archived = 0
    
    for archive_file in quant_logger.log_root.glob("*.tar.gz"):
        try:
            file_date = datetime.strptime(archive_file.stem, '%Y-%m-%d')
            age = (datetime.now() - file_date).days
            
            if age > days_to_keep:
                archive_file.unlink()
                archived += 1
        except ValueError:
            continue
    
    print(f"✅ 已清理 {archived} 个归档日志")


if __name__ == "__main__":
    # 测试日志
    print("🧪 测试日志功能...")
    
    log_execution("test-001", "data_fetch", 0.5, "success")
    log_data_fetch("momaapi", "600519", 30, 125.5, True)
    log_strategy("AI-网格策略", "买入", "603960", 26.15, 0.85)
    log_trade("BUY", "603960", "克莱机电", 100, 26.15, 0)
    log_risk_event("position_limit", "WARNING", "603960", "仓位超限 36.65%", {"weight": 36.65})
    log_performance("cpu_usage", 45.2, "%", {"process": "main_v3"})
    log_error("APIError", "MomaAPI timeout")
    
    print("✅ 日志测试完成")
    print(f"📁 日志目录: {quant_logger.log_root}")
