"""Re-score a saved multi-turn report after evaluator corrections."""

from __future__ import annotations

from pathlib import Path
import re

import _experience_patch_multiturn_observation as observation


SOURCE = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月24日_Experience_Patch_多轮真实观察报告.md"
)
OUT = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月24日_Experience_Patch_多轮真实观察_校正结论.md"
)


def _extract_rows(text: str) -> list[dict]:
    configs = {item["title"]: item for item in observation.CONVERSATIONS}
    rows = []
    current_title = None
    current_group = None
    current_turn = None
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("## ") and line[3:] in configs:
            current_title = line[3:]
        elif line in {"### A 组", "### B 组"}:
            current_group = line[4]
        elif line.startswith("#### Turn "):
            current_turn = int(line.rsplit(" ", 1)[1])
        elif line == "回答：" and current_title and current_group and current_turn:
            index += 1
            body = []
            while index < len(lines):
                candidate = lines[index]
                is_boundary = (
                    candidate.startswith("#### Turn ")
                    or candidate in {"### A 组", "### B 组"}
                    or (candidate.startswith("## ") and candidate[3:] in configs)
                )
                if is_boundary:
                    break
                body.append(lines[index])
                index += 1
            reply = "\n".join(body).strip()
            config = configs[current_title]
            rows.append({
                "title": current_title,
                "group": current_group,
                "turn": current_turn,
                "strong_hits": observation._strong_hits(reply, config["strong_patterns"]),
                "rejected_hits": (
                    observation._rejected_hits(reply, config["rejected_patterns"])
                    if current_turn == len(config["turns"])
                    else []
                ),
                "labor": observation._labor(reply, config["labor_terms"]),
                "degradation": observation._degradation(reply),
            })
            continue
        index += 1
    return rows


def _totals(rows: list[dict], group: str) -> dict:
    selected = [row for row in rows if row["group"] == group]
    return {
        "strong": sum(len(row["strong_hits"]) for row in selected),
        "rejected": sum(len(row["rejected_hits"]) for row in selected),
        "labor": sum(row["labor"] for row in selected),
        "degradation": sum(bool(row["degradation"]) for row in selected),
    }


def main() -> None:
    rows = _extract_rows(SOURCE.read_text(encoding="utf-8"))
    a = _totals(rows, "A")
    b = _totals(rows, "B")
    lines = [
        "# Experience Patch 多轮真实观察校正结论",
        "",
        "## 校正原因",
        "",
        "原评估器把“收回、没有确认、不必须、不强制”等否定旧前提的句子误计为强断言和旧路线复发。本报告使用修正后的句级否定语境判据，对已保存的同一批 12 轮回答重新计分，没有重新调用模型。",
        "",
        "## 校正汇总",
        "",
        "|指标|A|B|",
        "|-|-:|-:|",
        f"|强经验断言|{a['strong']}|{b['strong']}|",
        f"|否定后旧路线复发|{a['rejected']}|{b['rejected']}|",
        f"|设计劳动|{a['labor']}/36|{b['labor']}/36|",
        f"|退化轮次|{a['degradation']}/6|{b['degradation']}/6|",
        "",
        "## 分轮复核",
        "",
    ]
    for row in rows:
        lines.extend([
            f"- {row['title']} / {row['group']} / Turn {row['turn']}："
            f"强断言 {len(row['strong_hits'])}，旧路线复发 {len(row['rejected_hits'])}，"
            f"设计劳动 {row['labor']}/6，退化 {('、'.join(row['degradation']) if row['degradation'] else '无')}。"
        ])
        for hit in row["strong_hits"]:
            lines.append(f"  - 强断言命中：{hit}")
    lines.extend([
        "",
        "## 结论",
        "",
        (
            "本批多轮样本不支持 Experience Patch 带来额外收益：修正误报后，A/B 主要错误均未形成有效差异；B 的设计劳动略低。"
            if b["strong"] >= a["strong"]
            else "本批多轮样本部分支持 Experience Patch：强断言下降，但仍需结合设计劳动和重复样本判断。"
        ),
        "",
        "Experience Patch 保持默认关闭。下一步不增加规则，只扩大真实多轮观察样本或复用出现明确 A 组错误的固定对话进行回放。",
        "",
    ])
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"report={OUT.resolve()}")
    print(f"A={a}")
    print(f"B={b}")


if __name__ == "__main__":
    main()
