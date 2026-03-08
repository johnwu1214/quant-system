#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书消息推送模块
"""
import requests
import json
import os
from datetime import datetime

# 飞书机器人 Webhook（需要替换为你的实际 Webhook）
# 在飞书群聊中添加机器人后获取
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")

class FeishuNotifier:
    """飞书消息推送"""
    
    def __init__(self, webhook: str = None):
        self.webhook = webhook or FEISHU_WEBHOOK
    
    def send_text(self, text: str) -> bool:
        """发送文本消息"""
        if not self.webhook:
            print("⚠️ 未配置飞书 Webhook")
            return False
        
        url = self.webhook
        payload = {
            "msg_type": "text",
            "content": {
                "text": text
            }
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                print(f"✅ 消息发送成功: {text[:50]}...")
                return True
            else:
                print(f"❌ 发送失败: {response.text}")
                return False
        except Exception as e:
            print(f"❌ 发送异常: {e}")
            return False
    
    def send_trading_signal(self, stock_code: str, stock_name: str, 
                           signal: str, price: float, strategy: str,
                           reason: str = "") -> bool:
        """发送交易信号"""
        emoji = "🔔" if signal == "买入" else "🔕" if signal == "卖出" else "📊"
        
        text = f"""
{emoji} *量化交易信号*

📌 股票: {stock_name} ({stock_code})
🎯 信号: **{signal}**
💰 价格: ¥{price:.2f}
🧠 策略: {strategy}
📝 原因: {reason}

🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_text(text.strip())
    
    def send_daily_report(self, results: list) -> bool:
        """发送每日报告"""
        text = f"""
📊 *每日量化报告*

🕐 {datetime.now().strftime('%Y-%m-%d')}

"""
        for r in results:
            text += f"• {r['name']} ({r['code']}): {r['signal']} @ ¥{r['price']:.2f}\n"
        
        return self.send_text(text.strip())
    
    def send_error(self, error_msg: str) -> bool:
        """发送错误通知"""
        return self.send_text(f"❌ *量化系统错误*\n\n{error_msg}")


# 测试
if __name__ == "__main__":
    notifier = FeishuNotifier()
    
    # 测试发送
    # notifier.send_trading_signal(
    #     stock_code="600519",
    #     stock_name="贵州茅台",
    #     signal="买入",
    #     price=1850.50,
    #     strategy="MA5_20",
    #     reason="金叉形成，短期均线上穿长期均线"
    # )
    
    print("飞书通知模块已就绪")
    print("请设置 FEISHU_WEBHOOK 环境变量或在代码中配置 Webhook")
