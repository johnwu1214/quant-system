#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
quant-system web monitor (full version)
All 14 routes preserved + performance/nav_history
"""
import os, sys, json, subprocess, time
os.environ['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
from datetime import datetime
from flask import Flask, jsonify, render_template, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=None,
            instance_path=BASE_DIR)

PORTFOLIO_FILE = os.path.join(BASE_DIR, "..", "portfolio_state.json")
BLACKLIST_FILE = os.path.join(BASE_DIR, "..", "blacklist.json")
CONFIG_FILE    = os.path.join(BASE_DIR, "..", "trading_config.json")
DECISION_LOG   = os.path.join(BASE_DIR, "..", "decision_log.jsonl")
PERF_LOG       = os.path.join(BASE_DIR, "..", "performance_log.jsonl")
NAV_HISTORY    = os.path.join(BASE_DIR, "..", "nav_history.jsonl")
INTRADAY_PID   = "/tmp/intraday_v4_2.pid"

def read_json(path, default=None):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

# ── 14 routes ──────────────────────────────────────────────────────────
@app.route("/api/positions")
def api_positions():
    return jsonify(read_json(PORTFOLIO_FILE, {"cash": 0, "positions": {}}))

@app.route("/api/logs")
def api_logs():
    n = int(request.args.get("n", 50))
    records = []
    try:
        with open(DECISION_LOG, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        records = [json.loads(l.strip()) for l in lines[-n:] if l.strip()]
    except FileNotFoundError:
        pass
    return jsonify(list(reversed(records)))

@app.route("/api/blacklist")
def api_blacklist():
    return jsonify(read_json(BLACKLIST_FILE, {"stocks": []}))

@app.route("/api/status")
def api_status():
    running = False
    try:
        with open(INTRADAY_PID, 'r') as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        running = True
    except Exception:
        running = False
    return jsonify({"intraday_running": running, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})

@app.route("/api/config")
def api_config_get():
    return jsonify(read_json(CONFIG_FILE, {}))

@app.route("/api/config", methods=["POST"])
def api_config_post():
    try:
        data = request.get_json()
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/manual_trade", methods=["POST"])
def api_manual_trade():
    try:
        data = request.get_json()
        record = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                  "type": data.get("type",""), "code": data.get("code",""),
                  "shares": data.get("shares",0), "price": data.get("price",0),
                  "note": data.get("note",""), "manual": True}
        log_path = os.path.join(BASE_DIR, "..", "manual_trades.jsonl")
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return jsonify({"ok": True, "record": record})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/manual_trades")
def api_manual_trades():
    records = []
    try:
        with open(os.path.join(BASE_DIR, "..", "manual_trades.jsonl"), 'r') as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line.strip()))
    except FileNotFoundError:
        pass
    return jsonify(list(reversed(records)))

@app.route("/api/process/start", methods=["POST"])
def api_process_start():
    try:
        try:
            with open(INTRADAY_PID, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return jsonify({"ok": False, "message": f"已在运行 PID={pid}"})
        except Exception:
            pass
        log_file = os.path.join(BASE_DIR, "..", "logs", f"trading_{datetime.now().strftime('%Y%m%d')}.log")
        cmd = ["/root/qlib-venv/bin/python3", "-u", os.path.join(BASE_DIR, "..", "intraday_v4_2.py")]
        with open(log_file, 'a') as f:
            proc = subprocess.Popen(cmd, stdout=f, stderr=f)
        with open(INTRADAY_PID, 'w') as f:
            f.write(str(proc.pid))
        return jsonify({"ok": True, "pid": proc.pid})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/process/stop", methods=["POST"])
def api_process_stop():
    try:
        with open(INTRADAY_PID, 'r') as f:
            pid = int(f.read().strip())
        os.kill(pid, 9)
        return jsonify({"ok": True, "message": f"PID={pid} 已终止"})
    except Exception:
        return jsonify({"ok": False, "message": "进程未运行"})

@app.route("/api/run_risk_scanner", methods=["POST"])
def api_run_risk_scanner():
    try:
        sys.path.insert(0, os.path.join(BASE_DIR, ".."))
        from risk_scanner import scan_portfolio_risk
        result = scan_portfolio_risk()
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/performance")
def api_performance():
    records = []
    try:
        with open(PERF_LOG, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line.strip()))
    except FileNotFoundError:
        pass
    return jsonify(records[-30:])

@app.route("/api/nav_history")
def api_nav_history():
    records = []
    try:
        with open(NAV_HISTORY, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line.strip()))
    except FileNotFoundError:
        pass
    return jsonify(records[-30:])

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True, use_reloader=False)
