"""
local_search.py — ArchAI 本地知识检索工具

从 build_index.py 生成的向量索引检索，返回三类结构化结果：
    - 案例经验（case_strategy）
    - 理论依据（theory）
    - 设计方法（method）

供 server.py 的 /api/local_retrieve 调用（与 Dify 检索双轨并存）。
"""

import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

BASE = Path(__file__).resolve().parent
VECTOR_DIR = BASE / "vector_db"
MODEL_DIR = os.path.expanduser(
    r"~/.cache/modelscope/hub/models/BAAI/bge-small-zh-v1___5"
)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# 全局缓存：索引 + 模型（server 常驻时避免重复加载）
_INDEX = None
_MODEL = None


def _load_index() -> dict:
    """加载向量索引（embeddings.npy + metadata.json）"""
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    emb_path = VECTOR_DIR / "embeddings.npy"
    meta_path = VECTOR_DIR / "metadata.json"
    if not emb_path.exists() or not meta_path.exists():
        raise FileNotFoundError(
            f"索引不存在: {VECTOR_DIR}。请先运行 python build_index.py"
        )
    embeddings = np.load(emb_path)
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    _INDEX = {"embeddings": embeddings, "metadata": metadata}
    return _INDEX


def _load_model():
    """加载 BGE 模型（懒加载，仅首次调用时）"""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModel.from_pretrained(MODEL_DIR)
    model.to(DEVICE)
    model.eval()
    _MODEL = (tokenizer, model)
    return _MODEL


def _embed_query(query: str) -> np.ndarray:
    """单条查询 → 归一化向量 (1, 512)"""
    tokenizer, model = _load_model()
    inputs = tokenizer(
        [query], return_tensors="pt", padding=True, truncation=True, max_length=512
    )
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
    with torch.no_grad():
        output = model(**inputs)
    last_hidden = output.last_hidden_state
    mask = inputs["attention_mask"].unsqueeze(-1).float()
    mean_pooled = (last_hidden * mask).sum(1) / mask.sum(1)
    mean_pooled = torch.nn.functional.normalize(mean_pooled, p=2, dim=1)
    return mean_pooled.cpu().numpy().astype(np.float32)


def local_retrieve(query: str, top_k: int = 3, prefer_category: str | None = None) -> dict:
    """本地知识检索，返回三类结果。

    Args:
        query: 用户查询（中文）
        top_k: 每类返回数量
        prefer_category: 案例节点的优先类别（如 "strategy" 核心手法）。
                        若指定，案例结果优先返回该类别的节点；
                        不足 top_k 时用其他类别补足。

    Returns:
        {
            "cases": [{"name", "strategy", "content", "score"}],
            "theory": [{"name", "content", "score"}],
            "methods": [{"name", "content", "score"}],
        }
    """
    index = _load_index()
    embeddings = index["embeddings"]
    metadata = index["metadata"]

    # 查询向量
    q_vec = _embed_query(query)  # (1, 512)

    # 余弦相似度（已归一化，点积即余弦）
    sims = embeddings @ q_vec.T  # (N, 1)
    sims = sims.flatten()

    # 按类型分组
    type_indices = {"case_strategy": [], "theory": [], "method": [], "judgment_rule": [], "thinking_skill": []}
    for i, meta in enumerate(metadata):
        t = meta.get("type")
        if t in type_indices:
            type_indices[t].append(i)

    def top_in(ids: list[int], n: int, prefer: str | None = None) -> list[dict]:
        """在指定 id 子集中取相似度最高的 n 个。

        若 prefer 指定，且对应类别的节点够多，优先返回该类别。
        """
        if not ids:
            return []
        ranked = sorted(ids, key=lambda i: sims[i], reverse=True)
        results = []
        if prefer:
            # 优先收集 prefer 类别的节点
            preferred = [i for i in ranked if metadata[i].get("category") == prefer]
            fallback = [i for i in ranked if metadata[i].get("category") != prefer]
            ordered = preferred + fallback
        else:
            ordered = ranked
        for i in ordered[:n]:
            meta = metadata[i]
            item = {"score": round(float(sims[i]), 4)}
            if meta["type"] == "case_strategy":
                item["name"] = meta.get("case", "")
                item["strategy"] = meta.get("strategy", "")
                item["content"] = meta.get("content", "")
                item["category"] = meta.get("category", "")
            elif meta["type"] == "judgment_rule":
                # 判断原则：透传完整结构化字段（供判断层注入）
                item["id"] = meta.get("id", "")
                item["domain"] = meta.get("domain", "")
                item["project_type"] = meta.get("project_type", "")
                item["trigger"] = meta.get("trigger", "")
                item["facts"] = meta.get("facts", "")
                item["observation"] = meta.get("observation", "")
                item["impact"] = meta.get("impact", "")
                item["conditions"] = meta.get("conditions", "")
                item["forbidden"] = meta.get("forbidden", "")
                item["question"] = meta.get("question", "")
                item["content"] = meta.get("content", "")
            elif meta["type"] == "thinking_skill":
                item["id"] = meta.get("id", "")
                item["name"] = meta.get("name", "")
                item["domain"] = meta.get("domain", "")
                item["trigger"] = meta.get("trigger", "")
                item["goal"] = meta.get("goal", "")
                item["dimensions"] = meta.get("dimensions", "")
                item["forbidden"] = meta.get("forbidden", "")
                item["content"] = meta.get("content", "")
            else:
                item["name"] = meta.get("name", "")
                item["content"] = meta.get("content", "")
            # 来源标注（V1.1：可对证）
            item["source"] = meta.get("source", "")
            item["architect"] = meta.get("architect", "")
            item["built_year"] = meta.get("built_year", "")
            results.append(item)
        return results

    return {
        "cases": top_in(type_indices["case_strategy"], top_k, prefer_category),
        "theory": top_in(type_indices["theory"], top_k),
        "methods": top_in(type_indices["method"], top_k),
        "judgments": top_in(type_indices["judgment_rule"], top_k),
        "skills": top_in(type_indices["thinking_skill"], top_k),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ArchAI 本地知识检索")
    parser.add_argument("query", nargs="?", default="", help="检索关键词")
    parser.add_argument("--top_k", type=int, default=3)
    args = parser.parse_args()

    if not args.query:
        print("用法: python local_search.py <查询词> [--top_k 3]")
        print("示例: python local_search.py '创造校园共享交流空间'")
        sys.exit(1)

    print(f"查询: {args.query}")
    print(f"设备: {DEVICE}")
    t0 = time.time()
    result = local_retrieve(args.query, args.top_k)
    dt = time.time() - t0
    print(f"耗时: {dt*1000:.0f} ms\n")

    print("【案例经验】")
    for c in result["cases"]:
        print(f"  {c['name']} | {c['strategy']} | 相似度 {c['score']}")
        print(f"    {c['content'][:70]}...")
    print("\n【理论依据】")
    for t in result["theory"]:
        print(f"  {t['name']} | 相似度 {t['score']}")
        print(f"    {t['content'][:70]}...")
    print("\n【设计方法】")
    for m in result["methods"]:
        print(f"  {m['name']} | 相似度 {m['score']}")
        print(f"    {m['content'][:70]}...")
