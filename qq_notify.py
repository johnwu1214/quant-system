#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qq_notify.py - 兼容层，实际调用微信推送
（已迁移到微信渠道，此文件保留用于兼容旧调用）
用法: python3 qq_notify.py "消息内容"
"""
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from weixin_notify import send_weixin

    if __name__ == "__main__":
        if len(sys.argv) < 2:
            print("用法: python3 qq_notify.py '消息内容'")
            sys.exit(1)
        msg = " ".join(sys.argv[1:])
        # 兼容层：QQ调用转为微信推送
        send_weixin(msg)
        print("[提示] QQ推送已迁移至微信渠道")
except ImportError as e:
    print(f"[ERROR] 导入失败: {e}")
    sys.exit(1)
