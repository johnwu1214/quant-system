#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
knowledge_feeder.py - 知识投喂 + RAG查询 + 决策记录
用法:
  --text   "任意文本"          投喂文本笔记
  --file   /path/to/file.txt  投喂文件
  --decision "描述"            记录交易决策
  --query  "关键词"            检索知识库
"""

import argparse
import json
import uuid
import chromadb
from datetime import datetime, date
from pathlib import Path

BASE_DIR      = Path("/root/quant-system")
CHROMA_DIR    = BASE_DIR / "chroma_db"
DECISION_LOG  = BASE_DIR / "decision_log.jsonl"

chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
knowledge_col = chroma_client.get_or_create_collection("quant_knowledge")

def feed_text(text, category="note", source="manual"):
    doc_id = str(uuid.uuid4())
    today  = str(date.today())
    now    = datetime.now().strftime("%Y-%m-%d %H:%M")
    knowledge_col.add(
        ids=[doc_id], documents=[text],
        metadatas=[{"date": today, "time": now,
                    "category": category, "source": source}])
    print(f"✅ 已投喂 [{category}]: {text[:60]}...")
    return doc_id

def feed_file(filepath, category="research"):
    content = Path(filepath).read_text(encoding="utf-8")
    chunks  = [c.strip() for c in content.split("\n\n") if len(c.strip()) > 20]
    for chunk in chunks:
        feed_text(chunk[:500], category=category, source=filepath)
    print(f"✅ 文件投喂完成，{len(chunks)}个片段: {filepath}")

def log_decision(description, code="", action="", reason="", result=""):
    entry = {
        "date": str(date.today()),
        "time": datetime.now().strftime("%H:%M"),
        "code": code, "action": action,
        "reason": reason, "result": result,
        "description": description,
        # Fine-tune格式预留
        "prompt": f"市场状态:bull 股票:{code} 信号:{reason} 应该怎么做？",
        "completion": f"{action}。理由:{reason}。预期:{result}。"
    }
    with open(DECISION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    feed_text(description, category="decision", source="decision_log")
    # 统计当前记录数
    count = sum(1 for _ in open(DECISION_LOG, encoding="utf-8"))
    print(f"✅ 决策已记录（共{count}条，目标2000条）: {description[:60]}")

def query_knowledge(query, n_results=5):
    results = knowledge_col.query(
        query_texts=[query], n_results=n_results)
    items = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        items.append({"content": doc,
                      "date": meta.get("date"),
                      "category": meta.get("category")})
    return items

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="知识库投喂工具")
    parser.add_argument("--text",     help="投喂文本")
    parser.add_argument("--file",     help="投喂文件路径")
    parser.add_argument("--decision", help="记录交易决策")
    parser.add_argument("--query",    help="检索知识库")
    parser.add_argument("--category", default="note")
    parser.add_argument("--code",     default="")
    parser.add_argument("--action",   default="")
    parser.add_argument("--reason",   default="")
    parser.add_argument("--result",   default="")
    args = parser.parse_args()

    if args.text:
        feed_text(args.text, category=args.category)
    elif args.file:
        feed_file(args.file, category=args.category)
    elif args.decision:
        log_decision(args.decision, code=args.code,
                     action=args.action, reason=args.reason,
                     result=args.result)
    elif args.query:
        results = query_knowledge(args.query)
        print(f"\n🔍 检索结果（共{len(results)}条）:")
        for r in results:
            print(f"  [{r['date']}][{r['category']}] {r['content'][:100]}")
    else:
        parser.print_help()
