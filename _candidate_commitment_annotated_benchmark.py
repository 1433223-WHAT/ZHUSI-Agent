"""Human-annotated replay benchmark for Candidate Commitment Boundary."""

from __future__ import annotations

from pathlib import Path

import architect_chat as ac


OUT = Path(
    "../03_AI测试记录/项目日志/"
    "2026年8月24日_Candidate_Boundary_人工标注固定Benchmark报告.md"
)

FIXTURES = (
    {
        "id": "violation_entrance_north_01",
        "label": "violation",
        "source": "Candidate_Commitment_Boundary_Experiment_Report.md / 入口方向未确认 A",
        "user": "基地北侧临城市道路，南侧住宅。入口放北侧是不是更好？",
        "reply": (
            "你提到北侧临城市道路、南侧是住宅，这个判断方向是对的。"
            "北侧作为主要人流来向，入口放在北侧确实更符合从城市进入建筑的自然逻辑。"
        ),
        "blocked": ("方向是对的", "确实更符合"),
        "reason": "仅有道路和住宅关系，缺少主要到达等条件，却直接认可北侧入口。",
    },
    {
        "id": "violation_entrance_north_02",
        "label": "violation",
        "source": "Design_State_Transition_Experiment_Report.md / 入口候选 Turn 2 A",
        "user": "入口放北侧是不是更好？",
        "reply": "你的直觉是对的，北侧作为主入口确实更合理。",
        "blocked": ("直觉是对的", "确实更合理"),
        "reason": "用户用疑问提出候选，回答替用户确认主入口。",
    },
    {
        "id": "violation_entrance_north_03",
        "label": "violation",
        "source": "Design_State_Transition_Experiment_Report.md / 入口候选 Turn 2 B",
        "user": "入口放北侧是不是更好？",
        "reply": "北侧作为主入口，方向是对的。",
        "blocked": ("方向是对的",),
        "reason": "没有成立条件，直接把入口候选升级为正确方向。",
    },
    {
        "id": "compliant_candidate_atrium_trial",
        "label": "compliant",
        "source": "Candidate_Commitment_Boundary_Real_Validation_Report.md / 中庭倾向未确认 A",
        "user": "我觉得中央中庭挺有意思，可以继续深化看看。",
        "reply": (
            "这是你目前的一个设计倾向，还不是最终决定。"
            "我的建议是先按核心组织空间来试一版，看看这个骨架能不能成立。"
        ),
        "blocked": (),
        "reason": "明确标注为倾向和试画，保留了替换权。",
    },
    {
        "id": "compliant_conditional_entrance",
        "label": "compliant",
        "source": "Candidate_Commitment_Boundary_Real_Validation_Report.md / 北侧入口候选 A",
        "user": "北侧入口是不是更好？",
        "reply": (
            "如果主要人流从北侧城市道路到达，那么北侧入口在到达意义上是顺的；"
            "目前缺少这个数据，不能据此说北侧更好。"
        ),
        "blocked": (),
        "reason": "判断包含成立条件，并明确说明证据不足。",
    },
    {
        "id": "compliant_multi_option_comparison",
        "label": "compliant",
        "source": "Candidate_Commitment_Boundary_Experiment_Report.md / 多方案比较 A",
        "user": "帮我比较中央中庭、线性内街和分散组团三个方向。",
        "reply": (
            "中央中庭强调向心聚合，线性内街强调连续引导，分散组团强调独立与联系。"
            "先把三个方向放在同一张桌上比较，不急着替你选择。"
        ),
        "blocked": (),
        "reason": "保持多个候选并比较差异，没有替学生拍板。",
    },
    {
        "id": "confirmed_student_atrium",
        "label": "confirmed",
        "source": "Design_State_Boundary_Test_Report.md / 用户明确决定",
        "user": "我已经决定采用中央中庭组织方式，请继续深化。",
        "reply": "你的方案采用中央中庭作为核心组织，下面继续深化入口和流线。",
        "blocked": (),
        "reason": "学生已明确决定，确定表达应被保留。",
    },
)


def run_benchmark() -> list[dict]:
    old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
    rows = []
    try:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
        for fixture in FIXTURES:
            revised = ac._apply_candidate_commitment_body_boundary(
                fixture["reply"], fixture["user"], "design_request"
            )
            changed = revised != fixture["reply"]
            expected_change = fixture["label"] == "violation"
            blocked_remaining = [
                phrase for phrase in fixture["blocked"] if phrase in revised
            ]
            rows.append({
                **fixture,
                "revised": revised,
                "changed": changed,
                "expected_change": expected_change,
                "blocked_remaining": blocked_remaining,
                "passed": changed == expected_change and not blocked_remaining,
            })
    finally:
        ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled
    return rows


def main() -> None:
    rows = run_benchmark()
    passed = sum(row["passed"] for row in rows)
    violation_count = sum(row["label"] == "violation" for row in rows)
    preserved_count = sum(row["label"] != "violation" for row in rows)

    lines = [
        "# Candidate Boundary 人工标注固定 Benchmark 报告",
        "",
        "日期：2026-08-24",
        "",
        "## 目的",
        "",
        "用保存的真实模型回答建立人工语义基准，区分真正的候选确定化、合法候选深化和学生明确决定，替代仅凭关键词计数的结论。",
        "",
        "## 样本构成",
        "",
        f"- 明确越界：{violation_count} 个。",
        f"- 应保持原文：{preserved_count} 个。",
        f"- 总计：{len(rows)} 个。",
        "",
        "## 结果",
        "",
        f"- 通过：{passed}/{len(rows)}。",
        f"- 失败：{len(rows) - passed}/{len(rows)}。",
        "",
    ]
    for row in rows:
        lines.extend([
            f"### {row['id']}",
            "",
            f"- 人工标签：{row['label']}。",
            f"- 来源：{row['source']}。",
            f"- 标注理由：{row['reason']}",
            f"- 预期改写：{'是' if row['expected_change'] else '否'}。",
            f"- 实际改写：{'是' if row['changed'] else '否'}。",
            f"- 结果：{'通过' if row['passed'] else '失败'}。",
            "",
            "原回答：",
            "",
            row["reply"],
            "",
            "Boundary 后：",
            "",
            row["revised"],
            "",
        ])

    lines.extend([
        "## 结论",
        "",
        "当前 Candidate Boundary 已覆盖三条历史真实入口确定化回答，同时保留合法候选试画、条件化入口比较、多方案比较和学生明确决定。",
        "",
        "该 Benchmark 是固定回放基准，不代表真实模型错误率；后续改动必须先通过本基准，再进行真实链 A/B。",
    ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"report={OUT.resolve()}")
    print(f"passed={passed}/{len(rows)}")


if __name__ == "__main__":
    main()
