#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_notify_queue.py - 处理微信推送队列
由主 Agent 定时调用，或手动执行
"""
import sys
import os
import json
import glob
import subprocess
from datetime import datetime

QUEUE_DIR = "/root/quant-system/.notify_queue"
SENT_DIR = "/root/quant-system/.notify_sent"

def ensure_dirs():
    os.makedirs(QUEUE_DIR, exist_ok=True)
    os.makedirs(SENT_DIR, exist_ok=True)

def get_queue_files():
    """获取队列中的文件，按优先级排序"""
    if not os.path.exists(QUEUE_DIR):
        return []
    files = glob.glob(os.path.join(QUEUE_DIR, "*.json"))
    # high 优先级在前，然后按时间排序
    return sorted(files, key=lambda x: (
        0 if os.path.basename(x).startswith('high_') else 1,
        os.path.basename(x)
    ))

def send_via_openclaw(message, target, account_id, channel="openclaw-weixin"):
    """
    通过 OpenClaw CLI 发送消息
    """
    try:
        # 构建 openclaw message send 命令
        cmd = [
            "/root/.local/share/pnpm/openclaw", "message", "send",
            "--channel", channel,
            "--target", target,
            "-m", message
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr

    except Exception as e:
        return False, str(e)

def process_queue(dry_run=False, use_cli=True):
    """
    处理发送队列
    dry_run: 只打印不发送（用于测试）
    use_cli: 使用 openclaw CLI 发送
    返回: (成功数, 失败数, 消息列表)
    """
    ensure_dirs()
    files = get_queue_files()

    if not files:
        print("[队列] 没有待发送的消息")
        return 0, 0, []

    success_count = 0
    fail_count = 0
    messages = []

    print(f"[队列] 发现 {len(files)} 条待发送消息")

    for filepath in files:
        filename = os.path.basename(filepath)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            msg_content = data.get('message', '')
            priority = data.get('priority', 'normal')
            created_at = data.get('created_at', '')
            target = data.get('target', 'o9cq80yJxHbRLO8tbYzQlJu3IoJI@im.wechat')
            account_id = data.get('accountId', '46dec126a996-im-bot')

            messages.append({
                'filename': filename,
                'content': msg_content,
                'priority': priority,
                'created_at': created_at
            })

            print(f"\n[{priority.upper()}] {created_at}")
            print(f"内容预览: {msg_content[:80]}...")

            if dry_run:
                print("[DRY RUN] 未实际发送")
                continue

            # 实际发送
            if use_cli:
                success, output = send_via_openclaw(msg_content, target, account_id)
                if success:
                    print(f"[发送成功] {output[:100]}")
                else:
                    print(f"[发送失败] {output}")
                    fail_count += 1
                    continue

            # 移动到已发送目录
            sent_path = os.path.join(SENT_DIR, filename)
            os.rename(filepath, sent_path)
            success_count += 1

        except Exception as e:
            print(f"[ERROR] 处理 {filename} 失败: {e}")
            fail_count += 1

    return success_count, fail_count, messages

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    no_cli = "--no-cli" in sys.argv

    if dry_run:
        print("[模式] 试运行（不发送）")

    success, fail, msgs = process_queue(dry_run=dry_run, use_cli=not no_cli)

    print(f"\n{'='*40}")
    print(f"处理完成: 成功 {success}, 失败 {fail}")
