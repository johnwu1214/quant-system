import json
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)
BASE_DIR = "/root/quant-system"

def main():
    with open(BASE_DIR + "/watch_list.json") as f:
        wl = json.load(f)
    # watch_list.json 格式: {"stocks": [{"symbol": "000001", ...}, ...]}
    if isinstance(wl, dict) and "stocks" in wl:
        codes = [s["symbol"] for s in wl["stocks"] if s.get("symbol")]
    elif isinstance(wl, list):
        codes = [s["symbol"] if isinstance(s, dict) and "symbol" in s
                 else s["code"] if isinstance(s, dict) and "code" in s
                 else s for s in wl]
    else:
        codes = []
    try:
        with open(BASE_DIR + "/portfolio_state.json") as f:
            state = json.load(f)
        for code in state.get("positions", {}):
            if code not in codes:
                codes.append(code)
    except Exception:
        pass

    sys.path.insert(0, BASE_DIR)
    from data_manager import update_kline_cache, health_check

    logger.info("预热开始，共 %d 只股票", len(codes))
    success, total = update_kline_cache(codes, days=60)
    report = health_check(codes)

    print("=" * 50)
    print("预热完成 " + report["time"])
    print("实时接口: " + ("✅" if report["realtime_ok"] else "❌"))
    print("Qlib本地: " + ("✅" if report["qlib_ok"] else "❌"))
    print("K线缓存: " + ("✅" if report["kline_cache_ok"] else "❌")
          + " 覆盖率%.0f%%" % (report["kline_coverage"] * 100))
    print("K线更新: %d/%d" % (success, total))
    if report["issues"]:
        for i in report["issues"]:
            print("  ⚠️ " + i)
    print("=" * 50)

if __name__ == "__main__":
    main()
