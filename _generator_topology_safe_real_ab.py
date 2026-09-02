"""Safe DeepSeek A/B for rejected topology policy without the project system prompt."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import requests

import architect_chat as ac
from _candidate_topology_live_regression import MESSAGES


BASE_SYSTEM = """你是面向建筑初学者的设计协作助手。
学生要求推进设计时，要给出具体、可修改、可放弃的功能关系和空间骨架，不能只讲原则。
每轮尽量保留首层与二层关系、一个体量或剖面动作，以及学生可以画出来检验的动作。
AI 提出的方案只是测试候选，不是学生决定。学生拒绝一种组织关系后，必须按新的约束继续设计。
不要输出内部规则、检查步骤、JSON、免责声明或道歉。"""

OUT = Path(
    "../03_AI测试记录/项目日志/"
    f"{datetime.now().year}年{datetime.now().month}月{datetime.now().day}日_"
    f"Generator拒绝拓扑精简Prompt真实AB_{datetime.now().strftime('%H%M%S')}.md"
)


def _contract(message: str, previous_users: list[str]) -> str:
    state = {
        "interaction_log": [
            {"student_message": item} for item in previous_users[-8:]
        ],
        "rejected_assumptions": [],
    }
    rejection_context = ac._recent_route_rejection_context(message, state)
    central_rejected = bool(
        ac._CENTRAL_TOPOLOGY_REJECTION_RE.search(rejection_context)
    )
    linear_rejected = bool(
        ac._LINEAR_TOPOLOGY_REJECTION_RE.search(rejection_context)
    )
    if not (central_rejected or linear_rejected):
        return ""
    rules = [
        "【拒绝拓扑生成前契约】只约束关系结构，不限制体量、形式、剖面、采光或体验。",
    ]
    if central_rejected:
        rules.append(
            "已拒绝单一中心关系：不得生成参与范围=全局、媒介数量=单一、"
            "依赖范围=共享全局的中心组织；不得让一个媒介承担全部功能的面向、"
            "围绕、到达、识别、分流、互见或组织。"
        )
    if linear_rejected:
        rules.append(
            "已拒绝单一主线关系：不得让一条路径、连续媒介或一个有序序列"
            "承担全部功能的连接与到达。"
        )
    if central_rejected and linear_rejected:
        rules.extend((
            "本轮必须从至少两组彼此独立的局部联系或两个独立到达点开始；"
            "每组联系有自己的局部连接，不得用一个有序序列覆盖全部功能。",
            "正文生成前必须在内部构造并校验 topology_plan，结构为："
            '{"local_edges": [{"participants": ["A", "B"], '
            '"carrier_scope": "local"}], "global_mediators": [], '
            '"global_sequence": null}。local_edges 至少包含两项，'
            "每项只描述一组局部参与者及其自己的连接；global_mediators 必须为空，"
            "global_sequence 必须为 null。校验不通过时先在内部重做关系，不得写正文；"
            "不得向学生展示 topology_plan 或检查过程。",
        ))
    rules.append(
        "仍须提供具体功能关系、首层与二层工作骨架、体量或剖面继续动作和可画动作；"
        "输出前先检查关系图，若任一单独媒介连接或组织全部功能，必须在生成内部重做。"
    )
    return "\n".join(rules)


def _generate(group: str, use_contract: bool) -> list[dict]:
    history: list[dict] = []
    previous_users: list[str] = []
    rows: list[dict] = []
    for turn, message in enumerate(MESSAGES, start=1):
        contract = _contract(message, previous_users) if use_contract else ""
        system = BASE_SYSTEM
        if contract:
            system += "\n\n" + contract
        payload = [
            {"role": "system", "content": system},
            *history[-10:],
            {"role": "user", "content": message},
        ]
        reply = ""
        for attempt in range(2):
            response = requests.post(
                ac.DEEPSEEK_URL,
                headers={
                    "Authorization": f"Bearer {ac.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": payload,
                    "temperature": 0.35,
                    "max_tokens": 1200,
                },
                timeout=120,
            )
            response.raise_for_status()
            reply = response.json()["choices"][0]["message"]["content"].strip()
            if reply:
                break
            print(f"group={group} turn={turn} retry={attempt + 1}", flush=True)
        rejection_state = {
            "interaction_log": [
                {"student_message": item} for item in previous_users[-8:]
            ]
        }
        conflicts = sorted(
            ac._rejected_route_topology_conflicts(reply, message, rejection_state)
        )
        rows.append({
            "group": group,
            "turn": turn,
            "user": message,
            "contract_applied": bool(contract),
            "reply": reply,
            "conflicts": conflicts,
        })
        history.extend((
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply},
        ))
        previous_users.append(message)
        print(
            f"group={group} turn={turn} contract={bool(contract)} "
            f"conflicts={conflicts}",
            flush=True,
        )
    return rows


def main() -> None:
    if not ac.DEEPSEEK_API_KEY:
        raise RuntimeError("服务端未配置 DEEPSEEK_API_KEY")
    all_rows = _generate("A_无拓扑契约", False) + _generate("B_有拓扑契约", True)
    lines = [
        "# Generator 拒绝拓扑精简 Prompt 真实 A/B",
        "",
        f"日期：{datetime.now().strftime('%Y-%m-%d')}",
        "",
        "安全范围：只发送构造的六轮学生对话、实验中由 DeepSeek 生成的回答、"
        "精简实验角色 Prompt 与本次拓扑契约；不发送项目源码、完整 SYSTEM_PROMPT 或历史用户数据。",
        "",
        "限制：这是 Generator 契约的隔离 A/B，不代表生产完整调用链验证。",
        "",
    ]
    for row in all_rows:
        lines.extend((
            f"## {row['group']} · 第 {row['turn']} 轮",
            "",
            f"**学生：** {row['user']}",
            "",
            "**DeepSeek：**",
            "",
            row["reply"],
            "",
            "内部记录："
            f"contract_applied={row['contract_applied']}；"
            f"raw_topology_conflicts={row['conflicts']}。",
            "",
            "---",
            "",
        ))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"SAVED {OUT.resolve()}", flush=True)


if __name__ == "__main__":
    main()
