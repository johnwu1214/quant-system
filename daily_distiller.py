#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
daily_distiller.py - 每日记忆蒸馏系统
每日16:00运行，将当日所有信息蒸馏成结构化记忆
写入: 日记MD / ChromaDB向量库 / OpenClaw memory同步
"""

import json
import chromadb
from datetime import date, datetime
from pathlib import Path

BASE_DIR       = Path("/root/quant-system")
MEMORY_DIR     = BASE_DIR / "memory"
OPENCLAW_MEM   = Path("/root/.openclaw/workspace/memory")
OPENCLAW_PERMEM= Path("/root/.openclaw/workspace/MEMORY.md")
DECISION_LOG   = BASE_DIR / "decision_log.jsonl"
CHROMA_DIR     = BASE_DIR / "chroma_db"
PORTFOLIO_PATH = BASE_DIR / "portfolio_state.json"
INTEL_LOG      = BASE_DIR / "intelligence_log.json"

MEMORY_DIR.mkdir(exist_ok=True)
OPENCLAW_MEM.mkdir(parents=True, exist_ok=True)

chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
knowledge_col = chroma_client.get_or_create_collection(
    name="quant_knowledge",
    metadata={"hnsw:space": "cosine"})

def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return {}

def load_today_trades(today):
    trades = []
    if not DECISION_LOG.exists():
        return trades
    for line in DECISION_LOG.read_text().splitlines():
        try:
            e = json.loads(line)
            if e.get("date") == today:
                trades.append(e)
        except Exception:
            pass
    return trades

def distill_today():
    today   = str(date.today())
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*50}\n[DISTILL] 记忆蒸馏启动 {now_str}\n{'='*50}")
    fragments = []

    # 1. 情报扫描结果
    intel = load_json(INTEL_LOG)
    if intel:
        s = intel.get("summary", {})
        lines = [f"## 情报扫描 {intel.get('scan_date',today)}"]
        if s.get("high_risk"):
            lines.append(f"高风险: {', '.join(s['high_risk'])}")
        if s.get("medium_risk"):
            lines.append(f"中风险: {', '.join(s['medium_risk'])}")
        lines.append(f"正常: {', '.join(s.get('normal',[]))}")
        fragments.append(("intelligence", "\n".join(lines)))

    # 2. 持仓快照
    ps = load_json(PORTFOLIO_PATH)
    if ps:
        pos  = ps.get("positions", {})
        cash = ps.get("cash", 0)
        lines = [f"## 持仓快照 {today}"]
        for code, info in pos.items():
            if isinstance(info, dict):
                lines.append(f"- {code}: {info.get('shares',0)}股 "
                             f"成本{info.get('cost',0):.3f}")
            else:
                lines.append(f"- {code}: {info}")
        lines.append(f"- 现金: {cash:,.2f}元")
        fragments.append(("portfolio", "\n".join(lines)))

    # 3. 今日交易记录
    trades = load_today_trades(today)
    if trades:
        lines = ["## 今日交易"]
        for t in trades:
            lines.append(f"- [{t.get('action','?')}] {t.get('code','')} "
                        f"原因:{t.get('reason','未记录')} "
                        f"结果:{t.get('result','待观察')}")
        fragments.append(("trade", "\n".join(lines)))

    # 4. 写入日记文件
    diary_lines = [f"# 量化日记 {today}", f"> 生成: {now_str}", ""]
    for _, content in fragments:
        diary_lines.append(content)
        diary_lines.append("")
    diary_path = MEMORY_DIR / f"{today}.md"
    diary_path.write_text("\n".join(diary_lines), encoding="utf-8")
    print(f"[DISTILL] 日记写入: {diary_path}")

    # 5. 向量化存入ChromaDB
    for i, (category, content) in enumerate(fragments):
        doc_id = f"{today}_{category}_{i}"
        existing = knowledge_col.get(ids=[doc_id])
        if existing["ids"]:
            knowledge_col.update(ids=[doc_id], documents=[content],
                                 metadatas=[{"date": today, "category": category}])
        else:
            knowledge_col.add(ids=[doc_id], documents=[content],
                              metadatas=[{"date": today, "category": category}])
    print(f"[DISTILL] ChromaDB向量化完成，{len(fragments)}个片段")

    # 6. 同步到OpenClaw memory目录
    target = OPENCLAW_MEM / f"{today}.md"
    target.write_text(diary_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[DISTILL] 同步到OpenClaw: {target}")

    # 7. 高价值信息写入永久记忆MEMORY.md
    new_entries = []
    for category, content in fragments:
        if category == "intelligence" and "高风险" in content:
            new_entries.append(f"- [{today}] ⚠️ 风险事件: {content[:80]}")
        if category == "trade":
            new_entries.append(f"- [{today}] 💰 交易: {content[:80]}")
    if new_entries:
        existing_mem = OPENCLAW_PERMEM.read_text(encoding="utf-8") \
            if OPENCLAW_PERMEM.exists() else "# 量化系统永久记忆\n\n"
        OPENCLAW_PERMEM.write_text(
            existing_mem + "\n".join(new_entries) + "\n", encoding="utf-8")
        print(f"[DISTILL] 永久记忆新增 {len(new_entries)} 条")

    print(f"\n[DISTILL] ✅ 今日蒸馏完成: {today}")
    return diary_path

if __name__ == "__main__":
    distill_today()
