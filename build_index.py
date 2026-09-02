"""
build_index.py — ArchAI 本地知识索引构建工具

把本地知识（25案例 + 6理论 + 15方法）转为向量索引，供 local_search.py 使用。

架构：
    output/markdown/*/*.md   → 案例 → 拆成多个"策略节点"（case_strategy）
    knowledge/theory/*.md    → 理论卡片 → 1 节点（theory）
    knowledge/methods/*.md   → 方法卡片 → 1 节点（method）
            ↓
    BGE embedding (512维) + mean pooling + normalize
            ↓
    vector_db/embeddings.npy  +  vector_db/metadata.json

设计决策（对齐 Agent 工具调用）：
- 案例不存整篇正文，而是提取【设计问题/核心方法/适用场景/关联理论】标签
- 一个案例 = 多个策略节点（每个核心方法一个节点），让 AI 检索到"设计策略"而非"建筑百科"
- 不引入 faiss：数据量小（<100 节点），numpy 余弦相似度足够
"""

import io
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

BASE = Path(__file__).resolve().parent
OUTPUT_DIR = BASE / "output" / "markdown"
THEORY_DIR = BASE / "knowledge" / "theory"
METHODS_DIR = BASE / "knowledge" / "methods"
JUDGMENT_DIR = BASE / "output" / "judgment"
SKILLS_DIR = BASE / "output" / "skills"
VECTOR_DIR = BASE / "vector_db"

MODEL_DIR = os.path.expanduser(
    r"~/.cache/modelscope/hub/models/BAAI/bge-small-zh-v1___5"
)
MODEL_NAME = "BAAI/bge-small-zh-v1.5"
EMB_DIM = 512  # 已确认此 ModelScope 版本为 512 维

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# 案例章节中我们关心的标签
TAG_SECTIONS = ["设计问题", "核心方法", "适用场景", "关联理论"]


def setup_device() -> None:
    print(f"[INFO] 设备: {DEVICE}")
    if DEVICE == "cuda":
        print(f"       GPU: {torch.cuda.get_device_name(0)}")


def load_model():
    """加载 BGE 模型（优先本地缓存，其次 ModelScope 下载）"""
    print(f"[INFO] 加载模型 {MODEL_NAME} ...")
    if os.path.isdir(MODEL_DIR):
        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
        model = AutoModel.from_pretrained(MODEL_DIR)
        print(f"[INFO] 使用本地缓存: {MODEL_DIR}")
    else:
        # 兜底：从 ModelScope 下载
        from modelscope import snapshot_download
        model_dir = snapshot_download("BAAI/bge-small-zh-v1.5")
        tokenizer = AutoTokenizer.from_pretrained(model_dir)
        model = AutoModel.from_pretrained(model_dir)
    model.to(DEVICE)
    model.eval()
    return tokenizer, model


def extract_sections(md_text: str) -> dict:
    """从案例 markdown 提取各标签章节内容。

    按 '## 标题' 分割，返回 {章节名: 内容}。
    注意：标题可能带尾随空格（如"设计问题  "），需 strip。
    """
    sections = {}
    # 找所有 ## 标题
    matches = list(re.finditer(r"^## (.+)$", md_text, re.MULTILINE))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        content = md_text[start:end].strip()
        sections[title] = content
    return sections


def extract_source(md_text: str, sections: dict | None = None) -> dict:
    """从知识文件提取来源标注。

    返回 {"source": str, "architect": str, "built_year": str}
    - source：优先取"来源"/"资料来源"/"参考"章节原文（去掉 markdown 列表符号），
      没有则取"案例来源"/"案例关联"章节，都没有给兜底说明。
    - architect / built_year：从"基本信息"章节提取（案例专用）。
    """
    result = {"source": "", "architect": "", "built_year": ""}
    if sections is None:
        sections = extract_sections(md_text)

    # 1. 来源章节（案例："来源"；方法："案例来源"；理论："案例关联"）
    for key in ("来源", "资料来源", "参考来源", "案例来源", "案例关联", "参考资料"):
        content = sections.get(key, "")
        if content:
            # 清理 markdown 列表符号和空行
            cleaned = re.sub(r"^[-*]\s*", "", content, flags=re.MULTILINE).strip()
            result["source"] = cleaned[:500]
            break
    if not result["source"]:
        result["source"] = "项目自建教学整理，基于公开建筑资料，具体出处待补充。"

    # 2. 基本信息（建筑师 / 建成时间）
    info = sections.get("基本信息", "")
    if info:
        arch = re.search(r"建筑师[：:]\s*\*?\*?\s*([^\n*]+)", info)
        year = re.search(r"建成时间[：:]\s*\*?\*?\s*([^\n*]+)", info)
        if arch:
            result["architect"] = arch.group(1).strip()
        if year:
            result["built_year"] = year.group(1).strip()

    return result


def build_case_nodes(filepath: Path, case_name: str) -> list[dict]:
    """把一个案例拆成多个策略节点。

    Returns:
        节点列表，每个节点是一个 {type, case, category, strategy, content, source, architect, built_year} 字典
    """
    md_text = filepath.read_text(encoding="utf-8")
    sections = extract_sections(md_text)
    src = extract_source(md_text, sections)
    nodes = []

    def with_source(node: dict) -> dict:
        node["source"] = src["source"]
        node["architect"] = src["architect"]
        node["built_year"] = src["built_year"]
        return node

    # 1. 设计问题 → 1 节点
    problem = sections.get("设计问题", "")
    if problem:
        nodes.append(with_source({
            "type": "case_strategy",
            "case": case_name,
            "category": "problem",
            "strategy": "设计问题",
            "content": problem,
        }))

    # 2. 核心方法 → 每个方法 1 节点
    methods = sections.get("核心方法", "")
    if methods:
        # 按 "1. **方法名**：内容" 或 "- **方法名**：内容" 分割
        method_items = re.findall(r"^\d+\.\s*\*\*(.+?)\*\*[：:]\s*(.+)$", methods, re.MULTILINE)
        if not method_items:
            # 尝试无序号格式
            method_items = re.findall(r"[-*]\s*\*\*(.+?)\*\*[：:]\s*(.+)$", methods, re.MULTILINE)
        for name, desc in method_items:
            nodes.append(with_source({
                "type": "case_strategy",
                "case": case_name,
                "category": "strategy",
                "strategy": name.strip(),
                "content": f"{name}：{desc}".strip(),
            }))

    # 3. 适用场景 → 1 节点
    scenes = sections.get("适用场景", "")
    if scenes:
        nodes.append(with_source({
            "type": "case_strategy",
            "case": case_name,
            "category": "scene",
            "strategy": "适用场景",
            "content": f"适用场景：{scenes}".strip(),
        }))

    # 4. 关联理论 → 1 节点
    theory = sections.get("关联理论", "")
    if theory:
        nodes.append(with_source({
            "type": "case_strategy",
            "case": case_name,
            "category": "theory",
            "strategy": "关联理论",
            "content": f"关联理论：{theory}".strip(),
        }))

    return nodes


def build_card_node(type_: str, name: str, filepath: Path) -> dict:
    """理论/方法卡片 → 1 节点"""
    md_text = filepath.read_text(encoding="utf-8")
    sections = extract_sections(md_text)
    src = extract_source(md_text, sections)
    # 卡片核心：去标题，取正文（截断到 600 字，保留核心逻辑）
    body = md_text.strip()
    # 去掉首行 # 标题
    body = re.sub(r"^# .*\n+", "", body, flags=re.MULTILINE)
    content = body[:600]
    return {
        "type": type_,
        "name": name,
        "content": content,
        "source": src["source"],
    }


# 判断原则字段白名单（V0.1 设计规范 9 字段）
_JUDGMENT_FIELDS = (
    "ID", "问题类型", "触发维度", "事实输入", "观察",
    "可能影响", "依赖条件", "禁止推断", "需要学生决定",
)


def _parse_principle_block(block: str) -> dict:
    """解析单条判断原则（代码块内 '字段: 内容'，支持缩进续行）。

    block 形如：
        ```
        ID: RES-LIGHT-001
        问题类型: 住宅采光与朝向
        触发维度: 朝向 / 北向 ...
        ...
        ```
    """
    rule = {}
    current = None
    for line in block.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        m = re.match(r"^\s*([\u4e00-\u9fffA-Za-z]+):\s*(.*)$", line)
        if m and m.group(1) in _JUDGMENT_FIELDS:
            current = m.group(1)
            rule[current] = m.group(2).strip()
        elif current and line.strip().startswith(("-", "  ")):
            # 续行（列表项或缩进），追加到当前字段
            rule[current] += "\n" + line.strip()
    return rule


def build_judgment_nodes() -> list[dict]:
    """判断原则库（output/judgment/<类型>/<域>_*.md）→ 每条原则 1 节点。

    节点字段对齐设计规范：id/domain/trigger/facts/observation/impact/
    conditions/forbidden/question/project_type/content/source。
    """
    nodes = []
    for filepath in sorted(JUDGMENT_DIR.rglob("*.md")):
        md_text = filepath.read_text(encoding="utf-8")
        # 按 "## 原则 <ID>：<标题>" 分段
        blocks = re.split(r"^## 原则\s+", md_text, flags=re.MULTILINE)
        for block in blocks[1:]:
            # 块内找 ``` 代码块（原则字段在代码块里）
            code_m = re.search(r"```\n(.*?)\n```", block, re.DOTALL)
            if not code_m:
                continue
            rule = _parse_principle_block(code_m.group(1))
            rule_id = rule.get("ID", "").strip()
            if not rule_id:
                continue
            # 文件头元信息：项目类型前缀（目录名 RES/SCH/LIB）
            project_type = filepath.parent.name.upper()
            embed_text = " ".join(filter(None, [
                f"问题类型:{rule.get('问题类型','')}",
                f"触发维度:{rule.get('触发维度','')}",
                f"观察:{rule.get('观察','')}",
                f"可能影响:{rule.get('可能影响','')}",
                f"依赖条件:{rule.get('依赖条件','')}",
            ]))
            nodes.append({
                "type": "judgment_rule",
                "id": rule_id,
                "project_type": project_type,
                "domain": rule.get("问题类型", ""),
                "trigger": rule.get("触发维度", ""),
                "facts": rule.get("事实输入", ""),
                "observation": rule.get("观察", ""),
                "impact": rule.get("可能影响", ""),
                "conditions": rule.get("依赖条件", ""),
                "forbidden": rule.get("禁止推断", ""),
                "question": rule.get("需要学生决定", ""),
                "content": embed_text,
                "source": "筑思建筑设计判断层 V0.1（自建判断规则，非外部资料；仅作分析框架，不作结论依据）",
            })
    return nodes


def build_skill_nodes() -> list[dict]:
    """建筑思维 Skill 库（output/skills/<域>/SKILL_*.md）→ 每个 Skill 1 节点。

    Skill 回答"建筑师通常看什么"（观察维度菜单，不是执行顺序）。
    节点字段：id/name/domain/trigger/goal/dimensions/forbidden/content/source。
    """
    nodes = []
    for filepath in sorted(SKILLS_DIR.rglob("*.md")):
        md_text = filepath.read_text(encoding="utf-8")
        # ID：从首行 ## Skill 名（SKILL-SPATIAL-001）或标题提取
        id_m = re.search(r"SKILL-[A-Z]+-\d{3}", md_text)
        name_m = re.search(r"^## Skill 名称\s*\n(.+)$", md_text, re.MULTILINE)
        trigger_m = re.search(r"^## 触发场景\s*\n(.+)$", md_text, re.MULTILINE)
        goal_m = re.search(r"^## 目标\s*\n(.+?)(?=\n## )", md_text, re.DOTALL)
        dims_m = re.search(r"^## 观察维度.*?\n(.*?)(?=\n## )", md_text, re.DOTALL)
        forbid_m = re.search(r"^## AI 禁止行为\s*\n(.*?)(?=\n## )", md_text, re.DOTALL)
        skill_id = id_m.group(0) if id_m else filepath.stem
        name = (name_m.group(1).strip() if name_m else filepath.stem)
        trigger = trigger_m.group(1).strip() if trigger_m else ""
        goal = goal_m.group(1).strip() if goal_m else ""
        dimensions = dims_m.group(1).strip() if dims_m else ""
        forbidden = forbid_m.group(1).strip() if forbid_m else ""
        embed_text = " ".join(filter(None, [f"Skill:{name}", f"触发:{trigger}",
                                            f"观察维度:{dimensions[:400]}", f"目标:{goal[:200]}"]))
        nodes.append({
            "type": "thinking_skill",
            "id": skill_id,
            "name": name,
            "domain": filepath.parent.name.upper(),
            "trigger": trigger,
            "goal": goal[:300],
            "dimensions": dimensions[:600],
            "forbidden": forbidden[:400],
            "content": embed_text,
            "source": f"筑思建筑师思维 Skill 层 V0.1（来源：{name}；观察维度，非执行顺序）",
        })
    return nodes


def collect_all_nodes() -> list[dict]:
    """读取所有知识文件，生成节点列表（未向量化）。"""
    nodes = []

    # 1. 案例：递归扫 output/markdown/*/*.md
    case_count = 0
    for filepath in sorted(OUTPUT_DIR.rglob("*.md")):
        # 文件名：X_案例分析.md → X
        fname = filepath.stem
        case_name = fname.replace("_案例分析", "")
        case_nodes = build_case_nodes(filepath, case_name)
        nodes.extend(case_nodes)
        case_count += 1
    print(f"[INFO] 案例文件: {case_count} 个 → 策略节点: {len([n for n in nodes if n['type']=='case_strategy'])} 个")

    # 2. 理论卡片
    theory_count = 0
    for filepath in sorted(THEORY_DIR.glob("*.md")):
        name = filepath.stem
        nodes.append(build_card_node("theory", name, filepath))
        theory_count += 1
    print(f"[INFO] 理论卡片: {theory_count} 个")

    # 3. 方法卡片
    method_count = 0
    for filepath in sorted(METHODS_DIR.glob("*.md")):
        name = filepath.stem
        nodes.append(build_card_node("method", name, filepath))
        method_count += 1
    print(f"[INFO] 方法卡片: {method_count} 个")

    # 4. 判断原则（建筑设计判断层 V0.1）
    judgment_nodes = build_judgment_nodes()
    nodes.extend(judgment_nodes)
    print(f"[INFO] 判断原则: {len(judgment_nodes)} 个（output/judgment/）")

    # 5. 建筑思维 Skill（建筑师思维 Skill 层 V0.1）
    skill_nodes = build_skill_nodes()
    nodes.extend(skill_nodes)
    print(f"[INFO] 思维 Skill: {len(skill_nodes)} 个（output/skills/）")

    return nodes


def embed_texts(tokenizer, model, texts: list[str]) -> np.ndarray:
    """批量文本 → 向量 (n, 512)，mean pooling + normalize。"""
    if not texts:
        return np.zeros((0, EMB_DIM), dtype=np.float32)

    all_vecs = []
    batch_size = 16
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            inputs = tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )
            inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
            output = model(**inputs)
            last_hidden = output.last_hidden_state
            mask = inputs["attention_mask"].unsqueeze(-1).float()
            mean_pooled = (last_hidden * mask).sum(1) / mask.sum(1)
            mean_pooled = torch.nn.functional.normalize(mean_pooled, p=2, dim=1)
            all_vecs.append(mean_pooled.cpu().numpy())
    return np.concatenate(all_vecs, axis=0).astype(np.float32)


def main():
    setup_device()
    tokenizer, model = load_model()

    print("\n[1/3] 收集知识节点 ...")
    nodes = collect_all_nodes()
    print(f"[INFO] 总节点: {len(nodes)} 个")

    print("\n[2/3] 生成向量 ...")
    texts = []
    for n in nodes:
        if n["type"] == "case_strategy":
            texts.append(f"{n['case']} {n['strategy']} {n['content']}")
        elif n["type"] == "judgment_rule":
            texts.append(f"{n['id']} {n['content']}")
        elif n["type"] == "thinking_skill":
            texts.append(f"{n['id']} {n['content']}")
        else:
            texts.append(f"{n.get('name','')} {n['content']}")
    embeddings = embed_texts(tokenizer, model, texts)
    print(f"[INFO] 向量矩阵: {embeddings.shape}")

    print("\n[3/3] 保存索引 ...")
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    np.save(VECTOR_DIR / "embeddings.npy", embeddings)
    (VECTOR_DIR / "metadata.json").write_text(
        json.dumps(nodes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[INFO] 已保存: {VECTOR_DIR / 'embeddings.npy'}")
    print(f"[INFO] 已保存: {VECTOR_DIR / 'metadata.json'}")

    # 统计
    types = {}
    for n in nodes:
        types[n["type"]] = types.get(n["type"], 0) + 1
    print(f"\n✅ 索引构建完成！")
    print(f"   节点类型分布: {types}")
    print(f"   向量文件大小: {embeddings.nbytes/1024:.1f} KB")


if __name__ == "__main__":
    main()
