#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
东方财富爬虫 - 使用 Playwright
获取动态网页数据（资金流向、龙虎榜等）
"""
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional

# 尝试导入 Playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright 未安装")


class EastMoneyCrawler:
    """东方财富爬虫"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
    
    def start(self):
        """启动浏览器"""
        if not PLAYWRIGHT_AVAILABLE:
            print("⚠️ Playwright 不可用")
            return False
        
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=self.headless)
            self.context = self.browser.new_context()
            self.page = self.context.new_page()
            return True
        except Exception as e:
            print(f"⚠️ 浏览器启动失败: {e}")
            return False
    
    def close(self):
        """关闭浏览器"""
        if self.browser:
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()
    
    def get_money_flow(self, stock_code: str) -> Optional[Dict]:
        """获取资金流向"""
        if not self.page:
            return None
        
        try:
            url = f"https://quote.eastmoney.com/sh{stock_code}.html"
            if stock_code.startswith(("0", "3")):
                url = f"https://quote.eastmoney.com/sz{stock_code}.html"
            
            self.page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 提取主力资金流向
            data = self.page.evaluate("""
                () => {
                    const result = {};
                    // 尝试获取大单净流入
                    const mainFlow = document.querySelector('.main-flow');
                    if (mainFlow) {
                        result.main_flow = mainFlow.textContent.trim();
                    }
                    // 获取涨跌幅
                    const change = document.querySelector('.change .pct');
                    if (change) {
                        result.change_pct = change.textContent.trim();
                    }
                    return result;
                }
            """)
            
            return data if data else None
            
        except Exception as e:
            print(f"⚠️ 获取资金流向失败: {e}")
            return None
    
    def get_limit_up_pool(self, date: str = None) -> List[Dict]:
        """获取涨停池"""
        if not self.page:
            return None
        
        date = date or datetime.now().strftime("%Y%m%d")
        
        try:
            url = f"https://data.eastmoney.com/ztPool/ztPoolList_{date}.html"
            self.page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 提取涨停股票
            stocks = self.page.evaluate("""
                () => {
                    const results = [];
                    const rows = document.querySelectorAll('table tbody tr');
                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 5) {
                            results.push({
                                code: cells[1].textContent.trim(),
                                name: cells[2].textContent.trim(),
                                price: cells[3].textContent.trim(),
                                change: cells[4].textContent.trim()
                            });
                        }
                    });
                    return results;
                }
            """)
            
            return stocks[:50]  # 返回前50只
            
        except Exception as e:
            print(f"⚠️ 获取涨停池失败: {e}")
            return []
    
    def get_institutional_holding(self, stock_code: str) -> List[Dict]:
        """获取机构持仓"""
        if not self.page:
            return None
        
        try:
            url = f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax?code={stock_code}"
            self.page.goto(url, wait_until="networkidle", timeout=30000)
            
            data = self.page.evaluate("""
                () => {
                    try {
                        return JSON.parse(document.body.textContent);
                    } catch {
                        return null;
                    }
                }
            """)
            
            return data
            
        except Exception as e:
            print(f"⚠️ 获取机构持仓失败: {e}")
            return None
    
    def search_stock_news(self, stock_code: str, limit: int = 10) -> List[Dict]:
        """搜索股票新闻"""
        if not self.page:
            return []
        
        try:
            url = f"https://search.eastmoney.com/news?keyword={stock_code}"
            self.page.goto(url, wait_until="networkidle", timeout=30000)
            
            news = self.page.evaluate(f"""
                () => {{
                    const results = [];
                    const items = document.querySelectorAll('.news_list .item');
                    for (let i = 0; i < Math.min({limit}, items.length); i++) {{
                        const item = items[i];
                        const title = item.querySelector('.title');
                        const time = item.querySelector('.time');
                        if (title && time) {{
                            results.push({{
                                title: title.textContent.trim(),
                                url: title.href,
                                time: time.textContent.trim()
                            }});
                        }}
                    }}
                    return results;
                }}
            """)
            
            return news
            
        except Exception as e:
            print(f"⚠️ 搜索新闻失败: {e}")
            return []


class JuchaoCrawler:
    """巨潮资讯网爬虫 - 获取公告"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
    
    def start(self):
        if not PLAYWRIGHT_AVAILABLE:
            return False
        
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=self.headless)
            self.context = self.browser.new_context()
            self.page = self.context.new_page()
            return True
        except:
            return False
    
    def close(self):
        if self.browser:
            self.browser.close()
    
    def get_announcements(self, stock_code: str, days: int = 30) -> List[Dict]:
        """获取公司公告"""
        if not self.page:
            return []
        
        try:
            url = f"http://www.cninfo.com.cn/new/disclosure/stock?stockCode={stock_code}&orgId=gssz"
            self.page.goto(url, wait_until="networkidle", timeout=30000)
            
            announcements = self.page.evaluate(f"""
                () => {{
                    const results = [];
                    const items = document.querySelectorAll('.announcement');
                    for (let i = 0; i < Math.min({days * 2}, items.length); i++) {{
                        const item = items[i];
                        const title = item.querySelector('.title');
                        const time = item.querySelector('.time');
                        if (title && time) {{
                            results.push({{
                                title: title.textContent.trim(),
                                time: time.textContent.trim(),
                                url: title.href
                            }});
                        }}
                    }}
                    return results;
                }}
            """)
            
            return announcements
            
        except Exception as e:
            print(f"⚠️ 获取公告失败: {e}")
            return []


# 便捷函数
def crawl_money_flow(stock_code: str) -> Optional[Dict]:
    """快速获取资金流向"""
    crawler = EastMoneyCrawler(headless=True)
    if crawler.start():
        try:
            return crawler.get_money_flow(stock_code)
        finally:
            crawler.close()
    return None


def crawl_limit_up(date: str = None) -> List[Dict]:
    """快速获取涨停池"""
    crawler = EastMoneyCrawler(headless=True)
    if crawler.start():
        try:
            return crawler.get_limit_up_pool(date)
        finally:
            crawler.close()
    return []


# 测试
if __name__ == "__main__":
    print("🧪 测试 Playwright 爬虫...")
    
    if PLAYWRIGHT_AVAILABLE:
        # 测试资金流向
        print("\n💰 获取资金流向 (600519)...")
        crawler = EastMoneyCrawler(headless=True)
        if crawler.start():
            try:
                data = crawler.get_money_flow("600519")
                print(f"   结果: {data}")
            finally:
                crawler.close()
        else:
            print("   ⚠️ 启动失败")
    else:
        print("   ⚠️ Playwright 未安装")
        print("   安装: pip install playwright && playwright install chromium")
    
    print("\n✅ 爬虫模块测试完成")
