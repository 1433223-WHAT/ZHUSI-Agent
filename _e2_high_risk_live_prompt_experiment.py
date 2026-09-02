"""E2 high-risk jump DeepSeek live prompt A/B experiment.

Minimal prompt-only comparison:
- A: minimal tutor prompt + user sample
- B: minimal tutor prompt + E2 high-risk jump policy + same user sample

This does not run the full Agent pipeline: no state, no RAG, no boundary, no G
pre-output check, and no production system prompt. It reads the API key from
.env and never writes secrets.
"""
from __future__ import annotations

from pathlib import Path
import json

import requests


BASE = Path(__file__).resolve().parent
OUT = Path("output/e2_high_risk_live_prompt_experiment_20260821.md")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


def load_env() -> dict:
    env = {}
    path = BASE / ".env"
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.split("#", 1)[0].strip().strip('"').strip("'")
    return env


CASES = [
    {
        "id": "A",
        "title": "道路 -> 主入口 / 人流",
        "input": "我做一个幼儿园，基地北侧临城市道路，南侧是住宅区。现在想先讨论入口和活动场地的大致组织。你给我一版空间组织建议。",
        "watch": ["主入口", "主要人流", "北侧入口", "候选", "如果", "验证"],
    },
    {
        "id": "B",
        "title": "绿地 -> 安静 / 景观",
        "input": "我做一个社区儿童活动中心，基地东侧有一片城市绿地，西侧是城市支路。我想讨论儿童活动空间和周边环境的关系。你给我一版空间组织建议。",
        "watch": ["安静", "景观资源", "采光资源", "候选", "如果", "验证"],
    },
    {
        "id": "C",
        "title": "幼儿行为 -> 空间规则",
        "input": "我做一个6班幼儿园，需要服务3-6岁儿童，有日常活动、游戏和教师看护。你帮我推一下活动室、寝室和室外活动场地的关系。",
        "watch": ["必须", "不应该", "寝室", "活动室", "门禁", "验证"],
    },
]


MINIMAL_TUTOR_PROMPT = """你是一名建筑设计导师。

根据学生输入，给出一版可修改、可放弃的建筑设计建议。

要求：
- 推进设计。
- 给空间组织思路。
- 语言自然。
- 不要把回答变成审查报告。
"""


E2_POLICY = """E2 高风险经验跳跃检查（只检查三类，不检查所有设计判断）：
1. 道路/街道/城市支路 -> 主入口、主要人流、车行入口、接送入口。
2. 绿地/公园/庭院/景观边界 -> 安静面、景观资源、采光资源、适合安静功能。
3. 幼儿/儿童/照看/安全 -> 必须/不应该的空间规则。

如果出现上述跳跃，必须保留中间条件：
- 道路只能说明“有到达界面可能”，不能直接说明“主要人流来自这里”。
- 绿地只能说明“有潜在室外资源”，不能直接说明“安静、可借景、采光好”。
- 儿童行为只能说明“需要看护边界与管理验证”，不能直接推出“寝室不能接庭院”“活动室必须是枢纽”等规则。

推荐表达：
“如果……成立，可以暂时把……作为候选方向；但还需要验证……。”

禁止把回答改成五栏报告，禁止检查所有判断，禁止长篇免责声明。
仍然要给一版可修改、可放弃的空间组织建议。
"""


def call_model(user_input: str, with_e2: bool) -> str:
    key = load_env().get("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY in .env")
    messages = [{"role": "system", "content": MINIMAL_TUTOR_PROMPT}]
    if with_e2:
        messages.append({"role": "system", "content": E2_POLICY})
    messages.append({"role": "user", "content": user_input})
    resp = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": messages, "temperature": 0.35, "max_tokens": 1200},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def run_case(case: dict) -> dict:
    return {
        "case": case,
        "a": call_model(case["input"], with_e2=False),
        "b": call_model(case["input"], with_e2=True),
    }


def watch_hits(text: str, watch: list[str]) -> str:
    hits = [item for item in watch if item in (text or "")]
    return "、".join(hits) if hits else "（无直接命中）"


def build_report(results: list[dict]) -> str:
    parts = [
        "# E2 高风险经验跳跃 · DeepSeek live Prompt A/B 实验",
        "",
        "说明：本实验调用 DeepSeek live，但不跑完整 Agent；不使用 state、RAG、boundary、G pre-output check，也不发送完整生产系统提示。",
        "唯一变量：B 组在最小导师 Prompt 后追加 E2 高风险经验跳跃检查。",
        "不记录 API key，不输出请求头。",
        "",
    ]
    for item in results:
        case = item["case"]
        parts.extend([
            f"## 案例 {case['id']}：{case['title']}",
            "",
            f"**输入：** {case['input']}",
            "",
            "### A：最小导师 Prompt",
            "",
            f"**watch 命中：** {watch_hits(item['a'], case['watch'])}",
            "",
            item["a"],
            "",
            "### B：最小导师 Prompt + E2",
            "",
            f"**watch 命中：** {watch_hits(item['b'], case['watch'])}",
            "",
            item["b"],
            "",
            "---",
            "",
        ])
    parts.extend([
        "## 判读表（人工填写）",
        "",
        "| 样本 | A 高风险确定化 | B 高风险确定化 | B 保留设计劳动 | B 五栏化 | B 免责声明膨胀 | 判定 |",
        "|---|---|---|---|---|---|---|",
        "| A 道路 |  |  |  |  |  |  |",
        "| B 绿地 |  |  |  |  |  |  |",
        "| C 幼儿行为 |  |  |  |  |  |  |",
    ])
    return "\n".join(parts)


def write_report(results: list[dict], path: Path = OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report(results), encoding="utf-8")
    return path


def main() -> None:
    results = []
    for case in CASES:
        print(f"running case {case['id']} ...")
        results.append(run_case(case))
    path = write_report(results)
    print(f"done -> {path}")


if __name__ == "__main__":
    main()
