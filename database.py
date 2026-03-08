#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化交易系统 SQLite 数据库模块
支持数据存储、查询和分析
"""
import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
import pandas as pd
from contextlib import contextmanager


class QuantDatabase:
    """量化交易数据库"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "data", "quant_system.db")
        
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.init_schema()
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_schema(self):
        """初始化数据库表结构"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 行情数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    source TEXT DEFAULT 'unknown',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 2. 持仓表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    name TEXT,
                    quantity INTEGER,
                    avg_cost REAL,
                    current_price REAL,
                    unrealized_pnl REAL,
                    weight REAL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 3. 交易记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    name TEXT,
                    side TEXT CHECK(side IN ('BUY', 'SELL')),
                    quantity INTEGER,
                    price REAL,
                    commission REAL,
                    slippage REAL,
                    trade_time DATETIME,
                    strategy TEXT,
                    pnl REAL,
                    return_pct REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 4. 风控事件表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS risk_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    severity TEXT CHECK(severity IN ('INFO', 'WARNING', 'CRITICAL')),
                    symbol TEXT,
                    description TEXT,
                    triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    resolved_at DATETIME,
                    status TEXT DEFAULT 'active'
                )
            """)
            
            # 5. 信号记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    name TEXT,
                    signal_type TEXT,
                    signal_side TEXT,
                    price REAL,
                    confidence REAL,
                    strategy TEXT,
                    ai_strategy TEXT,
                    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    executed INTEGER DEFAULT 0
                )
            """)
            
            # 6. 性能指标表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_type TEXT NOT NULL,
                    metric_name TEXT,
                    value REAL,
                    unit TEXT,
                    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 7. 执行日志表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS execution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id TEXT,
                    start_time DATETIME,
                    end_time DATETIME,
                    total_duration REAL,
                    module_name TEXT,
                    duration REAL,
                    status TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 8. 系统指标表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    value REAL,
                    unit TEXT,
                    tags TEXT,
                    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time ON market_data(symbol, timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON trades(symbol, trade_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol_time ON signals(symbol, generated_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_events_time ON risk_events(triggered_at)")
            
            print("✅ 数据库表初始化完成")
    
    # ==================== 数据导入方法 ====================
    
    def import_market_data(self, symbol: str, data_file: str, source: str = "unknown"):
        """导入行情数据"""
        if not os.path.exists(data_file):
            print(f"⚠️ 文件不存在: {data_file}")
            return
        
        df = pd.read_csv(data_file)
        
        with self.get_connection() as conn:
            for _, row in df.iterrows():
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO market_data (symbol, timestamp, open, high, low, close, volume, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (symbol, row.get('date', datetime.now().isoformat()), 
                      row.get('open'), row.get('high'), 
                      row.get('low'), row.get('close'), 
                      row.get('volume'), source))
            
            print(f"✅ 已导入 {symbol} {len(df)} 条行情数据")
    
    def import_all_market_data(self, data_dir: str = None):
        """导入所有行情数据"""
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), "data")
        
        csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv') and f != 'kline_demo.png']
        
        for csv_file in csv_files:
            symbol = csv_file.replace('.csv', '')
            file_path = os.path.join(data_dir, csv_file)
            self.import_market_data(symbol, file_path, source="momaapi")
    
    def import_trades(self, trading_log_file: str):
        """导入交易记录"""
        if not os.path.exists(trading_log_file):
            print(f"⚠️ 文件不存在: {trading_log_file}")
            return
        
        with open(trading_log_file) as f:
            for line in f:
                if line.strip():
                    try:
                        trade = json.loads(line)
                        self.save_trade(trade)
                    except:
                        pass
    
    def save_trade(self, trade: dict):
        """保存单笔交易"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades (symbol, name, side, quantity, price, commission, slippage, trade_time, strategy, pnl, return_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.get('code'),
                trade.get('name'),
                trade.get('action', 'BUY'),
                trade.get('shares'),
                trade.get('price'),
                trade.get('commission', 0),
                trade.get('slippage', 0),
                trade.get('date'),
                trade.get('strategy', 'manual'),
                trade.get('profit', 0),
                trade.get('return_pct', 0)
            ))
    
    def save_position(self, position: dict):
        """保存持仓"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO positions (symbol, name, quantity, avg_cost, current_price, unrealized_pnl, weight, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position.get('code'),
                position.get('name'),
                position.get('shares'),
                position.get('avg_cost', position.get('cost')),
                position.get('current_price'),
                position.get('pnl', 0),
                position.get('weight', 0),
                datetime.now().isoformat()
            ))
    
    def save_signal(self, signal: dict):
        """保存信号"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO signals (symbol, name, signal_type, signal_side, price, confidence, strategy, ai_strategy, generated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.get('code'),
                signal.get('name'),
                signal.get('signal_type', 'technical'),
                signal.get('signal'),
                signal.get('price'),
                signal.get('confidence', 0.8),
                signal.get('strategy', 'AI-网格策略'),
                signal.get('ai_strategy'),
                datetime.now().isoformat()
            ))
    
    def save_risk_event(self, event: dict):
        """保存风控事件"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO risk_events (event_type, severity, symbol, description, triggered_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                event.get('type'),
                event.get('severity', 'WARNING'),
                event.get('code'),
                event.get('message', ''),
                event.get('timestamp', datetime.now().isoformat())
            ))
    
    def save_performance_metric(self, metric_type: str, metric_name: str, value: float, unit: str = ""):
        """保存性能指标"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO performance_metrics (metric_type, metric_name, value, unit, recorded_at)
                VALUES (?, ?, ?, ?, ?)
            """, (metric_type, metric_name, value, unit, datetime.now().isoformat()))
    
    # ==================== 查询方法 ====================
    
    def query_performance(self, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """查询交易绩效"""
        with self.get_connection() as conn:
            query = """
                SELECT 
                    symbol,
                    name,
                    COUNT(*) as trade_count,
                    SUM(CASE WHEN side='SELL' THEN quantity * price ELSE 0 END) as total_sell,
                    SUM(CASE WHEN side='BUY' THEN quantity * price ELSE 0 END) as total_buy,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl,
                    MAX(pnl) as max_pnl,
                    MIN(pnl) as min_pnl,
                    AVG(return_pct) as avg_return,
                    MAX(return_pct) as max_return,
                    MIN(return_pct) as min_return
                FROM trades
            """
            
            params = []
            if start_date and end_date:
                query += " WHERE trade_time BETWEEN ? AND ?"
                params = [start_date, end_date]
            
            query += " GROUP BY symbol"
            
            return pd.read_sql(query, conn, params=params if params else None)
    
    def query_positions(self) -> pd.DataFrame:
        """查询当前持仓"""
        with self.get_connection() as conn:
            return pd.read_sql("SELECT * FROM positions", conn)
    
    def query_signals(self, limit: int = 100) -> pd.DataFrame:
        """查询信号记录"""
        with self.get_connection() as conn:
            return pd.read_sql(f"SELECT * FROM signals ORDER BY generated_at DESC LIMIT {limit}", conn)
    
    def query_risk_events(self, start_date: str = None) -> pd.DataFrame:
        """查询风控事件"""
        with self.get_connection() as conn:
            if start_date:
                return pd.read_sql(
                    "SELECT * FROM risk_events WHERE triggered_at >= ? ORDER BY triggered_at DESC",
                    conn, params=[start_date]
                )
            return pd.read_sql("SELECT * FROM risk_events ORDER BY triggered_at DESC", conn)
    
    def query_daily_pnl(self, date: str = None) -> dict:
        """查询每日盈亏"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 买入总额
            cursor.execute("""
                SELECT SUM(quantity * price) as total FROM trades 
                WHERE side='BUY' AND trade_time LIKE ?
            """, (f"{date}%",))
            buy_total = cursor.fetchone()[0] or 0
            
            # 卖出总额
            cursor.execute("""
                SELECT SUM(quantity * price) as total FROM trades 
                WHERE side='SELL' AND trade_time LIKE ?
            """, (f"{date}%",))
            sell_total = cursor.fetchone()[0] or 0
            
            # 手续费
            cursor.execute("""
                SELECT SUM(commission + slippage) as total FROM trades 
                WHERE trade_time LIKE ?
            """, (f"{date}%",))
            cost = cursor.fetchone()[0] or 0
            
            return {
                "date": date,
                "buy_total": buy_total,
                "sell_total": sell_total,
                "net_flow": sell_total - buy_total,
                "cost": cost
            }
    
    # ==================== 统计分析 ====================
    
    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.03) -> float:
        """计算夏普比率"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT return_pct FROM trades WHERE return_pct IS NOT NULL")
            returns = [r[0] / 100 for r in cursor.fetchall()]
            
            if not returns:
                return 0
            
            avg_return = sum(returns) / len(returns)
            std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
            
            if std_return == 0:
                return 0
            
            # 年化
            sharpe = (avg_return - risk_free_rate / 252) / std_return * (252 ** 0.5)
            return round(sharpe, 2)
    
    def calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT trade_time, SUM(pnl) as cumulative_pnl
                FROM trades
                GROUP BY DATE(trade_time)
                ORDER BY trade_time
            """)
            
            trades = cursor.fetchall()
            if not trades:
                return 0
            
            peak = 0
            max_dd = 0
            
            for _, pnl in trades:
                cumulative = pnl or 0
                if cumulative > peak:
                    peak = cumulative
                dd = (peak - cumulative) / (peak + 100000) * 100 if peak > 0 else 0
                max_dd = max(max_dd, dd)
            
            return round(max_dd, 2)
    
    def get_summary(self) -> dict:
        """获取数据库统计摘要"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 记录数
            cursor.execute("SELECT COUNT(*) FROM market_data")
            market_data_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM positions")
            positions_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM trades")
            trades_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM signals")
            signals_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM risk_events")
            risk_events_count = cursor.fetchone()[0]
            
            # 交易统计
            cursor.execute("SELECT SUM(pnl) FROM trades")
            total_pnl = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT SUM(commission + slippage) FROM trades")
            total_cost = cursor.fetchone()[0] or 0
            
            return {
                "market_data_count": market_data_count,
                "positions_count": positions_count,
                "trades_count": trades_count,
                "signals_count": signals_count,
                "risk_events_count": risk_events_count,
                "total_pnl": round(total_pnl, 2),
                "total_cost": round(total_cost, 2),
                "sharpe_ratio": self.calculate_sharpe_ratio(),
                "max_drawdown": self.calculate_max_drawdown()
            }
    
    def print_summary(self):
        """打印统计摘要"""
        summary = self.get_summary()
        
        print("\n" + "="*50)
        print("📊 数据库统计摘要")
        print("="*50)
        
        print(f"\n📈 数据量:")
        print(f"   行情数据: {summary['market_data_count']} 条")
        print(f"   持仓记录: {summary['positions_count']} 条")
        print(f"   交易记录: {summary['trades_count']} 条")
        print(f"   信号记录: {summary['signals_count']} 条")
        print(f"   风控事件: {summary['risk_events_count']} 条")
        
        print(f"\n💰 绩效:")
        print(f"   总盈亏: ¥{summary['total_pnl']:,.2f}")
        print(f"   总成本: ¥{summary['total_cost']:,.2f}")
        print(f"   夏普比率: {summary['sharpe_ratio']}")
        print(f"   最大回撤: {summary['max_drawdown']}%")


def migrate_from_json():
    """从JSON文件迁移数据到SQLite"""
    db = QuantDatabase()
    
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    
    print("\n🔄 开始数据迁移...")
    
    # 导入行情数据
    print("\n📈 导入行情数据...")
    db.import_all_market_data(data_dir)
    
    # 导入交易记录
    print("\n📝 导入交易记录...")
    trading_log = os.path.join(data_dir, "trading_log.json")
    if os.path.exists(trading_log):
        db.import_trades(trading_log)
    
    # 导入风控事件
    print("\n🛡️ 导入风控事件...")
    risk_file = os.path.join(data_dir, "risk_control.json")
    if os.path.exists(risk_file):
        with open(risk_file) as f:
            risk_data = json.load(f)
            for event in risk_data.get("风控规则触发", {}).get("checks_detail", []):
                db.save_risk_event({
                    "type": event.get("type"),
                    "severity": "WARNING" if not event.get("passed", True) else "INFO",
                    "code": event.get("code"),
                    "message": f"{event.get('type')}: {event.get('code')}",
                    "timestamp": event.get("timestamp")
                })
    
    # 导入信号
    print("\n📡 导入信号...")
    signal_file = os.path.join(data_dir, "strategy_performance.json")
    if os.path.exists(signal_file):
        with open(signal_file) as f:
            signal_data = json.load(f)
            for sig in signal_data.get("信号生成", {}).get("signals", []):
                db.save_signal(sig)
    
    # 打印统计
    db.print_summary()
    
    print("\n✅ 数据迁移完成!")
    return db


if __name__ == "__main__":
    migrate_from_json()
