#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weixin_notify.py - 通过微信渠道主动推送消息
用法: python3 weixin_notify.py "消息内容"
       python3 weixin_notify.py --title "标题" "消息内容"

实际实现：将消息写入待发送队列，由主 Agent 读取并发送
"""
import sys
import os
import json
from datetime import datetime

# 配置
TARGET_USER = "o9cq80yJxHbRLO8tbYzQlJu3IoJI@im.wechat"
ACCOUNT_ID = "46dec126a996-im-bot"
QUEUE_DIR = "/root/quant-system/.notify_queue"

def ensure_queue_dir():
    """确保队列目录存在"""
    os.makedirs(QUEUE_DIR, exist_ok=True)

def send_weixin(text, title=None, priority="normal"):
    """
    将消息加入发送队列
    priority: normal | high (高风险消息用 high)
    """
    try:
        ensure_queue_dir()

        # 构建消息内容
        if title:
            full_text = f"【{title}】\n{text}"
        else:
            full_text = text

        # 构建消息文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{priority}_{timestamp}.json"
        filepath = os.path.join(QUEUE_DIR, filename)

        message_data = {
            "channel": "openclaw-weixin",
            "target": TARGET_USER,
            "accountId": ACCOUNT_ID,
            "message": full_text,
            "created_at": datetime.now().isoformat(),
            "priority": priority
        }

        with open(filepath, "w") as f:
            json.dump(message_data, f, ensure_ascii=False, indent=2)

        print(f"[微信] 消息已加入队列: {filename}")
        return True

    except Exception as e:
        print(f"[ERROR] 微信推送失败: {e}")
        return False

def process_queue():
    """
    处理发送队列（由主 Agent 或定时任务调用）
    返回: 发送成功的消息数量
    """
    ensure_queue_dir()
    sent_count = 0

    # 按优先级排序（high 优先）
    files = sorted(os.listdir(QUEUE_DIR))

    for filename in files:
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(QUEUE_DIR, filename)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # 这里可以通过调用 OpenClaw API 或 message 工具发送
            # 目前只是打印，实际发送需要外部处理
            print(f"[待发送] {data['message'][:50]}...")

            # 发送成功后删除文件
            # os.remove(filepath)
            sent_count += 1

        except Exception as e:
            print(f"[ERROR] 处理 {filename} 失败: {e}")

    return sent_count

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 weixin_notify.py '消息内容'")
        print("  python3 weixin_notify.py --title '标题' '消息内容'")
        print("  python3 weixin_notify.py --process-queue  # 处理队列")
        sys.exit(1)

    if sys.argv[1] == "--process-queue":
        count = process_queue()
        print(f"[队列] 处理了 {count} 条消息")
        sys.exit(0)

    title = None
    priority = "normal"

    if sys.argv[1] == "--title" and len(sys.argv) >= 3:
        title = sys.argv[2]
        msg = " ".join(sys.argv[3:])
    elif sys.argv[1] == "--high" and len(sys.argv) >= 2:
        priority = "high"
        msg = " ".join(sys.argv[2:])
    elif sys.argv[1] == "--high" and sys.argv[2] == "--title" and len(sys.argv) >= 4:
        priority = "high"
        title = sys.argv[3]
        msg = " ".join(sys.argv[4:])
    else:
        msg = " ".join(sys.argv[1:])

    success = send_weixin(msg, title, priority)
    sys.exit(0 if success else 1)
