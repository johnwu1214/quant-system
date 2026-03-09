#!/bin/bash
# 量化交易脚本包装器 - intraday_v4_2.py
# 添加启动和结束钉钉通知

QUANT_GROUP="chat:cidjWkNIGDdL1GLCB0JRoifHg=="
SCRIPT_NAME="intraday_v4_2.py"
LOG_FILE="logs/trading_$(date +%Y%m%d).log"

# 确保日志目录存在
mkdir -p logs

# 发送启动通知
export PATH="/root/.nvm/versions/node/v22.22.0/bin:$PATH"
openclaw message send --agent quant --to "$QUANT_GROUP" --message "⏰ 量化系统启动：${SCRIPT_NAME} 开始运行，时间：$(date '+%Y-%m-%d %H:%M:%S')"

# 记录启动日志
echo "=== 量化系统启动：${SCRIPT_NAME} 时间：$(date) ===" >> "$LOG_FILE"

# 运行主脚本
cd /root/quant-system
/usr/bin/python3 "$SCRIPT_NAME" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

# 记录结束日志
echo "=== 量化系统结束：${SCRIPT_NAME} 退出码：${EXIT_CODE} 时间：$(date) ===" >> "$LOG_FILE"

# 发送结束通知
if [ $EXIT_CODE -eq 0 ]; then
    openclaw message send --agent quant --to "$QUANT_GROUP" --message "✅ 量化系统结束：${SCRIPT_NAME} 运行完毕，时间：$(date '+%Y-%m-%d %H:%M:%S')"
else
    openclaw message send --agent quant --to "$QUANT_GROUP" --message "❌ 量化系统异常：${SCRIPT_NAME} 运行失败（退出码：${EXIT_CODE}），时间：$(date '+%Y-%m-%d %H:%M:%S')"
fi

exit $EXIT_CODE
