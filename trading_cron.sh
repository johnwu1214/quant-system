#!/bin/bash
# A股交易定时任务 - 每5分钟执行一次
# 设置: crontab -e
# */5 9-11,13-15 * * 1-5 cd ~/quant_system && /usr/bin/python3 intraday_v2.py >> intraday_cron.log 2>&1

cd /Users/john.wu/quant_system

# 检查是否在交易时间
HOUR=$(date +%H)
MIN=$(date +%M)

# 转换为分钟
TOTAL_MIN=$((10#$HOUR * 60 + 10#$MIN))

# 交易时间: 9:30-11:30 (570-690) 和 13:00-15:00 (780-900)
if [ "$TOTAL_MIN" -ge 570 ] && [ "$TOTAL_MIN" -lt 690 ]; then
    echo "=== 上午交易时段 $(date) ==="
    /usr/bin/python3 intraday_v2.py >> intraday_cron.log 2>&1
elif [ "$TOTAL_MIN" -ge 780 ] && [ "$TOTAL_MIN" -lt 900 ]; then
    echo "=== 下午交易时段 $(date) ==="
    /usr/bin/python3 intraday_v2.py >> intraday_cron.log 2>&1
else
    echo "$(date) 非交易时间,跳过"
fi
