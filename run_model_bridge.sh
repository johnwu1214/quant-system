#!/bin/bash
# 每日收盘后运行 model_bridge，更新候选股池
LOG="/root/quant-system/logs/model_bridge_$(date +%Y%m%d).log"
mkdir -p /root/quant-system/logs

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 开始运行 model_bridge ===" >> $LOG

docker run --rm \
    -v /root/qlib_data/cn_data_community:/root/.qlib/qlib_data/cn_data_community \
    -v /root/quant-system:/root/quant-system \
    pyqlib/qlib_image_stable:stable \
    bash -c "cd /qlib && python setup.py build_ext --inplace -q 2>/dev/null && python3 /root/quant-system/model_bridge.py" \
    >> $LOG 2>&1

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 运行完成 ===" >> $LOG
