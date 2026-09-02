"""intent_router.py — 筑思 Agent 意图路由器（Intent Router V1.1）

作用：根据用户消息 + 当前状态，判断协作模式，决定"这一轮走什么流程"。
这是筑思从"有边界的聊天模型"走向"根据设计状态选择协作模式的 Agent"的第一层。

职责边界（V1.1 设计文档）：
- 只决定"这轮怎么组织输入"（澄清？验证？深化？检索？），不改变证据分层、设计判断边界。
- 只读 state，不写 confirmed；分类失败静默降级，不影响聊天主流程。
- 路由输出写入 process_record，供比赛展示可解释性。

架构位置：
    chat_turn → classify(message, state) → route(classification, state) → 按 pre_action 组织流程 → LLM
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent


def _load_env() -> dict:
    env = {}
    path = BASE / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.split("#", 1)[0].strip().strip('"').strip("'")
    return env


ENV = _load_env()
DEEPSEEK_API_KEY = ENV.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

CLASSIFY_PROMPT = """你是筑思Agent的意图路由器。请判断用户最近一条消息的类型，只输出 JSON。

判断维度：
1. intent（问题类型）：
   - design_review：评价/分析已有方案（含模糊评价如"空间很平""入口太普通"）
   - design_request：用户明确请求设计协助（"帮我设计一下""给我一个框架""给我一个方案起点"）——本轮应产出可修改的示范性骨架，不应走 clarify/request_vision 拦截
   - knowledge_query：建筑知识查询（案例/理论/方法，了解案例本身）
   - case_image_query：用户要查看知识库中某案例的视觉资料（"光之教堂图片""给我看看金贝尔平面图""有没有住吉长屋的图"）
   - case_transfer：用户想把某案例的手法迁移到自己的设计（"参考光之教堂设计教学楼""借鉴金贝尔的手法"）——注意与 knowledge_query（了解案例）区分：case_transfer 带有"迁移/用在自己项目"的意图
   - design_development：推进/深化设计
   - task_brief：新任务或需求描述
   - clarify_confirm：澄清/确认/修改/撤销此前内容
   - off_topic：与建筑无关

2. design_stage：concept（概念）/ development（深化）/ review（评图）/ undecided（未定）

3. info_status（结合当前已确认事实判断，4 类独立不合并）：
   - sufficient：信息足以支撑判断
   - insufficient：缺资料（如不知道建筑面积）——行为是补资料/问用户
   - conflicting：与已有事实冲突
   - needs_verification：已有判断但需验证（如"大厅可能导致流线交叉"）——行为是给验证动作，不是问用户

4. decision_status（决策状态）：
   - exploring：探索——开放比较各方向
   - considering：倾向——有倾向但未拍板
   - decided：已拍板——学生已作决定，应进入深化

5. needs（辅助需求，数组，可多选）：
   - clarify：需要先澄清
   - vision：需要看图纸/图片
   - case_search / theory_search / method_search：需要检索
   - none

规则：
- 用户消息是"帮我设计/帮我做/给我一个框架/给我一个方案起点/设计一下"等明确请求设计协助时，判为 design_request，info_status=sufficient（请求本身即授权），needs 不含 clarify，reason 标注"设计协助请求：应输出可修改示范骨架"
- 区分三种"案例相关"意图：了解案例本身（knowledge_query，"光之教堂为什么采光"）、要案例图片（case_image_query，"光之教堂图片"）、把案例手法用在自己项目（case_transfer，"参考光之教堂设计教学楼""想借鉴金贝尔的手法"）。case_transfer 的特征是出现设计对象（教学楼/图书馆等）或"参考/借鉴/模仿/迁移/像…一样"等迁移词
- 区分两种"图"：要知识库案例的视觉资料（case_image_query，如"光之教堂图片""金贝尔平面图""住吉长屋的照片"）vs 上传自己的图让 AI 分析（design_review，如"帮我看看这张图""我这个平面怎么样"）
- 区分两类"模糊"：设计评价模糊（"有点平""太普通""感觉不对"）→ design_review + insufficient + clarify；目标/期望表达（"排前列""拿高分""竞赛""评比""得奖"）是学生对作品的目标，判 design_development，needs 不含 clarify，reason 标注"目标表达：拆解可评价维度"，不要套用空间评价澄清模板
- 模糊评价（"有点平""太普通""感觉不对"）必须判为 design_review + insufficient + clarify，不要当成设计指令
- "我考虑X"与"我决定X"决策状态不同：考虑→considering，决定→decided
- 具体验证问题（"我的大厅会不会导致流线混乱"）判为 needs_verification，不是 insufficient
- 用户消息已包含具体信息（功能清单、场地条件、动静关系等）时，即使历史状态为空，也应判 sufficient，不要 clarify——例如"功能上有阅览、儿童区、活动室，儿童区和活动室吵"是足够的信息
- 判断 sufficient/insufficient 必须结合用户消息本身的内容，不只依赖 state_summary
- 不要编造用户没说的设计意图
- 只输出 JSON，不要解释

用户消息：{message}
当前已确认事实：{state_summary}"""

# 可用的 intent / info_status / decision_status 白名单（防 LLM 输出未知值）
VALID_INTENTS = {"design_review", "design_request", "knowledge_query", "case_image_query", "case_transfer", "design_development", "task_brief", "clarify_confirm", "off_topic"}
VALID_STAGES = {"concept", "development", "review", "undecided"}
VALID_INFO = {"sufficient", "insufficient", "conflicting", "needs_verification"}
VALID_DECISION = {"exploring", "considering", "decided"}
VALID_NEEDS = {"clarify", "vision", "case_search", "theory_search", "method_search", "none"}


def _extract_json(text: str) -> dict:
    """从 LLM 响应提取 JSON（复用 task_analyzer 的成熟模式）。"""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {}


def _sanitize(classification: dict) -> dict:
    """白名单清洗：过滤 LLM 输出的未知枚举值，保证下游 route 只遇到合法值。"""
    def pick(value, allowed, default):
        return value if value in allowed else default

    needs = classification.get("needs", [])
    if isinstance(needs, str):
        needs = [needs]
    if not isinstance(needs, list):
        needs = []
    clean_needs = [n for n in needs if n in VALID_NEEDS] or ["none"]
    return {
        "intent": pick(classification.get("intent"), VALID_INTENTS, "design_development"),
        "design_stage": pick(classification.get("design_stage"), VALID_STAGES, "undecided"),
        "info_status": pick(classification.get("info_status"), VALID_INFO, "sufficient"),
        "decision_status": pick(classification.get("decision_status"), VALID_DECISION, "exploring"),
        "needs": clean_needs,
        "reason": str(classification.get("reason", ""))[:200],
    }


def default_classification() -> dict:
    """降级分类：分类器失败时使用，行为等价于现有 chat_turn 默认路径。"""
    return {
        "intent": "design_development",
        "design_stage": "undecided",
        "info_status": "sufficient",
        "decision_status": "exploring",
        "needs": ["none"],
        "reason": "分类器不可用，降级为默认协作模式",
    }


def state_summary(state: dict | None) -> str:
    """从 state 提取已确认事实的简短摘要（Router 只读，不写）。"""
    if not state:
        return ""
    project = state.get("project") or {}
    parts = []
    for key, value in project.items():
        if isinstance(value, dict) and value.get("value"):
            parts.append(f"{key}:{value['value']}")
    return "；".join(parts[:12]) or "（暂无已确认事实）"


def classify(message: str, state: dict | None = None) -> dict | None:
    """LLM 分类。失败或超时返回 None（调用方静默降级）。"""
    if not DEEPSEEK_API_KEY:
        return None
    prompt = CLASSIFY_PROMPT.format(
        message=message[:400],
        state_summary=state_summary(state)[:500],
    )
    try:
        resp = requests.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": message[:400]},
                ],
                "temperature": 0.1,
                "max_tokens": 200,
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = _extract_json(resp.json()["choices"][0]["message"]["content"])
        return _sanitize(raw) if raw else None
    except Exception as exc:
        print(f"[intent_router] 分类失败，静默降级: {type(exc).__name__}: {exc}")
        return None


def route(message: str, state: dict | None = None, classification: dict | None = None) -> dict:
    """路由决策：分类结果 → pre_action。

    pre_action 取值：
      clarify        — 先澄清评价维度（不调 LLM，用自然模板）
      method_check   — 给验证动作（画图/查证），不是问用户补资料
      request_vision — 引导上传图纸
      direct         — 正常走 LLM 对话
    """
    cls = _sanitize(classification) if classification else default_classification()
    intent = cls["intent"]
    info = cls["info_status"]
    decision = cls["decision_status"]
    needs = cls["needs"]

    pre_action = "direct"
    pre_question = ""
    clarify_target = ""

    # clarify 前置排除：强语境词（谁在评价）与强设计信息词（具体设计点）
    strong_context = re.search(r"老师|导师|评图|甲方|评委", message)
    strong_design = re.search(
        r"屋顶|木|结构|柱子|墙|窗|保留|拆|层高|面积|尺寸|材料|砖|梁|钢|地基|楼梯|天窗|"
        r"流线|采光|朝向|"
        r"排前列|拿高分|得奖|竞赛|评比|名次|获奖|评分|要求|任务书|标准",
        message,
    )
    has_concrete_info = strong_context or strong_design
    is_counter_question = re.search(r"你觉得呢|换你|你怎么看|你来说|要是你|你的意思|你说呢", message)
    # 模糊评价句信号（"入口太普通""门厅太窄""有点平"）——即使含部位词也应澄清
    is_vague_review = re.search(
        r"太\w+|太平|太空|太散|太窄|太挤|太满|太乱|有点|不够|普通|一般|单调|平淡|无聊|感觉不对|没感觉",
        message,
    )
    # 弱具体信号：朝向/数量/方位/部位等（"入口朝南开""三层""中庭旁边"）——非评价句时放行
    weak_concrete = re.search(
        r"朝\w+|朝南|朝北|朝东|朝西|面向|南向|北向|东向|西向|层|个|间|平米|平方|"
        r"旁边|前面|左边|右边|中间|入口|门厅|中庭|大厅|走廊|房间|教室|办公室",
        message,
    )

    # V2：案例视觉资料意图（case_image_query）——与"上传分析"彻底分流
    # ① 消息含案例名 + 图类词（"光之教堂图片""金贝尔平面图"）
    # ② 上一轮是案例图片查询，本轮承接（"有平面的吗""图呢""你从知识库里找"）
    from case_entities import find_case_entity as _find_entity
    prev_case_image = bool((state or {}).get("retrieval_focus", {}).get("intent") == "case_image_query")
    _wants_case_assets = (
        intent == "case_image_query"
        or (re.search(r"图片|平面图|剖面图|照片|效果图|透视图|有没有.{0,8}的图|看看.{0,8}的图|给我.{0,6}的图", message)
            and bool(_find_entity(message)))
        or (prev_case_image and re.search(r"平面|剖面|照片|空间|室内|效果|图", message))
    )
    # 承接案例上下文的知识问题（"这张图里的光是怎么处理的""光之教堂怎么采光"）→ direct，走继承检索+LLM
    prev_has_focus = bool((state or {}).get("retrieval_focus", {}).get("case"))
    _explicit_visual_reference = bool(re.search(r"这张图|图纸|平面图|剖面图|照片|图片|我画的", message))
    # 上传分析信号：承接案例上下文时，"这张图"指代已展示的案例资产，不算用户上传的图
    _wants_upload_analysis = bool(
        _explicit_visual_reference
        and re.search(
            r"帮我看看|分析这张|看看我的|我画的|上传|这张图|图纸|平面图|剖面图|照片|图片",
            message,
        )
    )
    # 案例迁移意图：含迁移词 + 案例名（"参考光之教堂设计教学楼"）
    _wants_case_transfer = bool(
        re.search(r"参考|借鉴|模仿|迁移|像.{0,8}一样|学习.{0,8}(手法|案例)", message) and _find_entity(message)
    )
    # 案例迁移延续：transfer_focus 存在且消息是兴趣/承接表达 → 继续走 case_transfer 流程（防 LLM 自由发挥越权）
    _in_transfer = bool((state or {}).get("transfer_focus", {}).get("stage") in ("observe", "interest"))
    _transfer_followup = _in_transfer and re.search(
        r"喜欢|感兴趣|吸引|光|材料|空间|路径|氛围|明暗|几何|嗯|可以|对|继续|那个|它|不知道|没想好", message
    )
    _knowledge_question = re.search(r"怎么|如何|为什么|是什么|有什么区别|之间的关系|的作用|的原理|的原理是什么", message)
    _has_live_design_route = any(
        isinstance(item, dict) and item.get("status") in {"proposed", "candidate", "active", "optional"}
        for item in ((state or {}).get("issue_register") or {}).values()
    ) or bool(((state or {}).get("design_focus") or {}).get("topic"))
    _design_continuation = bool(
        _has_live_design_route
        and re.search(r"继续|接着|往下|深化|展开|具体(?:一点|些)?|再推|接着弄", message)
    )
    _declares_no_visual = bool(re.search(
        r"(?:没有|没|无)(?:可|有)?(?:上传|画|提供)?(?:的)?(?:图|图纸|草图|平面图)|"
        r"(?:没有|没)(?:有)?(?:画|上传|提供).{0,6}(?:图|图纸|草图|平面图)",
        message,
    ))
    _rejects_design_route = bool(re.search(
        r"(?:不采用|不继续|不想继续|放弃|放掉|停止|收起|收回来|退回|换掉).{0,24}(?:方向|路线|方案|组织|分法|骨架)|"
        r"(?:方向|路线|方案|组织|分法|骨架).{0,16}(?:不采用|不继续|放弃|放掉|停止|收起|收回来|退回|换掉)",
        message,
    ))
    _verbal_design_feedback = bool(
        (not _explicit_visual_reference or _declares_no_visual)
        and re.search(
            r"没有图|没图|无图|只是口头|口头说|不想继续|不采用|放弃|"
            r"换个角度|换一个角度|不以.{0,20}为前提|"
            r"从整体|回到整体|退回整体|整体关系",
            message,
        )
    ) or _rejects_design_route

    if _wants_case_assets and not _wants_upload_analysis:
        pre_action = "case_image_query"
        pre_question = ""
    elif intent == "design_request":
        pre_action = "direct"  # 设计协助请求：直接产出可修改示范骨架，不 clarify、不 request_vision
        pre_question = ""
    elif _wants_case_transfer or _transfer_followup:
        pre_action = "case_transfer"  # 案例迁移：先调案例实体展示，分阶段讨论，防"隐形路线"
        pre_question = ""
    elif _design_continuation and not _explicit_visual_reference:
        pre_action = "direct"  # 已有候选的文字深化不应被误判为必须上传图纸
        pre_question = ""
    elif _verbal_design_feedback:
        pre_action = "direct"  # 口头评价/否定路线不是图纸分析请求，不得强制上传
        pre_question = ""
    elif _wants_upload_analysis:
        pre_action = "request_vision"
        pre_question = "这张图/方案的判断需要结合图纸。可以先上传平面草图或照片，我会只分析图中可见的内容，不替你改方案。"
    elif prev_has_focus and _knowledge_question and not _wants_upload_analysis:
        pre_action = "direct"  # 承接案例的知识问题 → 继承检索已提供案例知识，交 LLM
        pre_question = ""
    elif intent == "design_review" and info == "insufficient" and not is_counter_question:
        if is_vague_review and not has_concrete_info:
            pre_action = "clarify"  # 纯评价句无具体信息：入口太普通 / 门厅有点挤
            clarify_target = _clarify_target(message)
            pre_question = _clarify_question(message, clarify_target)
        elif is_vague_review and has_concrete_info:
            pre_action = "direct"  # 评价句 + 强具体词（评图老师/采光/流线）→ 具体问题，交 LLM
            pre_question = ""
        elif not has_concrete_info and not weak_concrete:
            pre_action = "clarify"  # 完全模糊且无任何具体信号
            clarify_target = _clarify_target(message)
            pre_question = _clarify_question(message, clarify_target)
        # 否则：含强具体信息或弱具体信号（朝南/三层/部位+想法）→ 交 LLM（direct）
    elif intent == "design_review" and info == "needs_verification":
        pre_action = "method_check"
        pre_question = _method_check_question(message)
    elif "vision" in needs:
        pre_action = "request_vision"
        pre_question = "这张图/方案的判断需要结合图纸。可以先上传平面草图或照片，我会只分析图中可见的内容，不替你改方案。"
    elif info == "conflicting":
        pre_action = "direct"
        pre_question = ""  # 冲突交给 LLM context 处理（注入 conflicting 提示）

    return {
        "pre_action": pre_action,
        "pre_question": pre_question,
        "clarify_target": clarify_target,
        "classification": cls,
        "retrieval_targets": [n for n in needs if n in {"case_search", "theory_search", "method_search"}],
        "reply_mode": "guided" if pre_action != "direct" else "normal",
    }


# ── 自然模板（不调 LLM，保持导师感）──────────────────────────────

_CLARIFY_TARGETS = (
    ("空间体验", "空间体验、尺度感或心理感受"),
    ("功能组织", "功能分区、流线组织或房间关系"),
    ("视觉表达", "立面、材料、造型或图面表达"),
    ("场地关系", "与场地、周边环境或入口的关系"),
)


def _clarify_target(message: str) -> str:
    """从模糊评价中推断最可能的澄清维度（启发式，仅用于模板选词）。"""
    text = message
    if re.search(r"流线|动线|交通|路径", text):
        return "功能组织"
    if re.search(r"立面|造型|材料|外观|颜色", text):
        return "视觉表达"
    if re.search(r"入口|场地|周边|朝向|采光", text):
        return "场地关系"
    if re.search(r"层高|高度|尺度|开阔|压抑", text):
        return "空间体验"
    return "空间体验"


def _clarify_question(message: str, target: str) -> str:
    """生成澄清追问（模板 + 具体化，不用通用禁句）。"""
    label = dict(_CLARIFY_TARGETS).get(target, "空间体验、功能组织或视觉表达")
    brief = message.strip().rstrip("。！？!?")[:40]
    return f"你提到“{brief}”，我想先确认一下：你指的是{label}上的问题，还是别的维度？这样我才能帮你分析，而不是凭猜测给建议。"


def _method_check_question(message: str) -> str:
    """生成验证动作引导（不是问用户补资料）。"""
    brief = message.strip().rstrip("。！？!?")[:40]
    return (
        f"关于“{brief}”，这个担心值得用图来验证，而不是直接给结论。"
        "你可以先画一张关系图：把相关功能/空间画成圆圈，标出人流方向和可能交叉的位置，"
        "再检查交叉点是否真的会造成冲突——画完我们可以对着图判断它是否成立。"
    )
