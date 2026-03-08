#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财报分析模块
自动解析和分析上市公司财报
"""
import os
import sys
import re
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class FinancialAnalyzer:
    """财报分析器"""
    
    def __init__(self):
        # 财务指标阈值
        self.thresholds = {
            "pe": {"low": 0, "high": 50, "safe": 30},
            "pb": {"low": 0, "high": 5, "safe": 3},
            "roe": {"low": 10, "high": 30, "safe": 15},
            "gross_margin": {"low": 20, "high": 50, "safe": 30},
            "net_margin": {"low": 5, "high": 30, "safe": 10},
            "debt_ratio": {"low": 0, "high": 70, "safe": 50},
            "current_ratio": {"low": 1.5, "high": 999, "safe": 2},
            "quick_ratio": {"low": 1, "high": 999, "safe": 1.5},
        }
    
    def analyze_financials(self, financials: Dict) -> Dict:
        """分析财务数据"""
        result = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "score": 0,
            "ratios": {},
            "alerts": [],
            "recommendation": "持有",
            "details": {}
        }
        
        # 计算各项指标
        for metric, value in financials.items():
            if metric in self.thresholds:
                ratio = self._evaluate_ratio(metric, value)
                result["ratios"][metric] = {
                    "value": value,
                    "status": ratio["status"],
                    "score": ratio["score"]
                }
                result["score"] += ratio["score"]
                
                if ratio["alert"]:
                    result["alerts"].append(ratio["alert"])
        
        # 综合评分 (满分100)
        max_score = len(result["ratios"]) * 25
        result["score"] = int(result["score"] / max_score * 100) if max_score > 0 else 50
        
        # 给出建议
        result["recommendation"] = self._get_recommendation(result["score"], result["alerts"])
        
        # 详细分析
        result["details"] = self._generate_details(result)
        
        return result
    
    def _evaluate_ratio(self, metric: str, value: float) -> Dict:
        """评估单个指标"""
        threshold = self.thresholds.get(metric, {})
        
        if metric in ["pe", "pb", "debt_ratio"]:
            # 越低越好
            if value < threshold.get("safe", 0):
                return {"status": "优秀", "score": 25, "alert": None}
            elif value < threshold.get("high", 0):
                return {"status": "正常", "score": 15, "alert": None}
            else:
                return {"status": "偏高", "score": 5, "alert": f"{metric.upper()}偏高: {value}"}
        else:
            # 越高越好
            if value > threshold.get("safe", 0):
                return {"status": "优秀", "score": 25, "alert": None}
            elif value > threshold.get("low", 0):
                return {"status": "正常", "score": 15, "alert": None}
            else:
                return {"status": "偏低", "score": 5, "alert": f"{metric.upper()}偏低: {value}"}
    
    def _get_recommendation(self, score: int, alerts: List) -> str:
        """获取建议"""
        if score >= 80 and len(alerts) == 0:
            return "强烈买入"
        elif score >= 60 and len(alerts) <= 1:
            return "买入"
        elif score >= 40:
            return "持有"
        elif score >= 20:
            return "减仓"
        else:
            return "卖出"
    
    def _generate_details(self, result: Dict) -> str:
        """生成详细分析"""
        details = []
        
        if result["score"] >= 80:
            details.append("✅ 财务状况优秀")
        elif result["score"] >= 60:
            details.append("✅ 财务状况良好")
        elif result["score"] >= 40:
            details.append("⚠️ 财务状况一般")
        else:
            details.append("❌ 财务状况堪忧")
        
        # 检查各项指标
        for metric, data in result["ratios"].items():
            if data["status"] == "优秀":
                details.append(f"✅ {metric.upper()}: {data['value']} ({data['status']})")
            elif data["status"] == "偏低" or data["status"] == "偏高":
                details.append(f"⚠️ {metric.upper()}: {data['value']} ({data['status']})")
        
        return "\n".join(details)
    
    def compare_industry(self, financials: Dict, industry_avg: Dict) -> Dict:
        """行业对比"""
        comparison = {}
        
        for metric, value in financials.items():
            if metric in industry_avg:
                avg = industry_avg[metric]
                ratio = value / avg if avg != 0 else 1
                comparison[metric] = {
                    "company": value,
                    "industry_avg": avg,
                    "ratio": ratio,
                    "status": "高于行业" if ratio > 1 else "低于行业"
                }
        
        return comparison
    
    def detect_anomalies(self, financials: Dict, history: List[Dict]) -> List[Dict]:
        """检测异常"""
        anomalies = []
        
        if not history:
            return anomalies
        
        # 获取上一期数据
        last = history[-1]
        
        # 检查营收变化
        if "revenue" in financials and "revenue" in last:
            change = (financials["revenue"] - last["revenue"]) / last["revenue"] * 100
            if abs(change) > 50:
                anomalies.append({
                    "metric": "revenue",
                    "type": "突变",
                    "change": f"{change:+.1f}%",
                    "severity": "high" if abs(change) > 100 else "medium"
                })
        
        # 检查利润变化
        if "profit" in financials and "profit" in last:
            if last["profit"] > 0:
                change = (financials["profit"] - last["profit"]) / last["profit"] * 100
                if change < -50:
                    anomalies.append({
                        "metric": "profit",
                        "type": "下滑",
                        "change": f"{change:+.1f}%",
                        "severity": "high" if change < -80 else "medium"
                    })
        
        # 检查负债变化
        if "debt_ratio" in financials and "debt_ratio" in last:
            change = financials["debt_ratio"] - last["debt_ratio"]
            if change > 20:
                anomalies.append({
                    "metric": "debt_ratio",
                    "type": "激增",
                    "change": f"+{change:.1f}%",
                    "severity": "high"
                })
        
        return anomalies
    
    def generate_report(self, stock_code: str, stock_name: str, 
                       financials: Dict, industry_avg: Dict = None,
                       history: List[Dict] = None) -> str:
        """生成完整财报分析报告"""
        # 分析
        analysis = self.analyze_financials(financials)
        
        # 行业对比
        industry_comp = None
        if industry_avg:
            industry_comp = self.compare_industry(financials, industry_avg)
        
        # 异常检测
        anomalies = []
        if history:
            anomalies = self.detect_anomalies(financials, history)
        
        # 生成报告
        report = f"""
📊 财报分析报告 - {stock_name} ({stock_code})
{'='*50}
分析日期: {analysis['date']}
综合评分: {analysis['score']}/100
投资建议: {analysis['recommendation']}

{'='*50}
财务指标
{'='*50}
"""
        
        for metric, data in analysis["ratios"].items():
            emoji = "✅" if data["status"] == "优秀" else "⚠️" if data["status"] in ["偏低", "偏高"] else "➖"
            report += f"{emoji} {metric.upper()}: {data['value']} ({data['status']})\n"
        
        if industry_comp:
            report += f"""
{'='*50}
行业对比
{'='*50}
"""
            for metric, data in industry_comp.items():
                report += f"  {metric.upper()}: 公司{data['company']} vs 行业{data['industry_avg']} ({data['status']})\n"
        
        if anomalies:
            report += f"""
{'='*50}
⚠️ 异常预警
{'='*50}
"""
            for a in anomalies:
                severity = "🔴" if a["severity"] == "high" else "🟡"
                report += f"{severity} {a['metric']}: {a['type']} {a['change']}\n"
        
        if analysis["alerts"]:
            report += f"""
{'='*50}
风险提示
{'='*50}
"""
            for alert in analysis["alerts"]:
                report += f"  ⚠️ {alert}\n"
        
        report += f"""
{'='*50}
{analysis['details']}
{'='*50}
🦞 自动生成 | 仅供参考
"""
        
        return report


# 测试
if __name__ == "__main__":
    analyzer = FinancialAnalyzer()
    
    # 模拟财务数据
    financials = {
        "pe": 15,
        "pb": 2.5,
        "roe": 18,
        "gross_margin": 35,
        "net_margin": 12,
        "debt_ratio": 45,
        "current_ratio": 2.0,
        "quick_ratio": 1.5
    }
    
    # 行业平均
    industry_avg = {
        "pe": 20,
        "pb": 3,
        "roe": 12,
        "gross_margin": 25,
        "net_margin": 8,
        "debt_ratio": 50
    }
    
    print("📊 测试财报分析...")
    report = analyzer.generate_report("600519", "贵州茅台", financials, industry_avg)
    print(report)
    
    print("\n✅ 财报分析模块测试完成")
