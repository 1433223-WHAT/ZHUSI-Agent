"""Trusted conversation memory for the ArchAI collaborative chat."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re

from collaboration_focus import empty_focus


PROJECT_FIELDS = ("project_type", "site", "users", "functions", "scale", "goals", "constraints")


_CLAUSE_SEPARATOR_RE = re.compile(r"[，,。！？!?；;\n]+")
_NEGATED_RETRACTION_RE = re.compile(
    r"(?:不是|并非|没有|并没有|没(?:有)?)(?:要|想|在|说)?"
    r"[^，,。！？!?；;\n]{0,16}(?:撤销|取消|收回|不算|不作数|推翻|先不确定)"
)


def retraction_signal_text(text: str) -> str:
    """只保留可能表达真实撤销意图的分句，排除“不是撤销”一类否定说明。"""
    clauses = _CLAUSE_SEPARATOR_RE.split(text or "")
    return "，".join(
        clause for clause in clauses
        if clause.strip() and not _NEGATED_RETRACTION_RE.search(clause)
    )


# ── 元对话与设计状态隔离（A：支持混合意图）────────────────────────────
# 用户输入可能同时包含"对 AI 行为/系统/上轮输出的反馈"和"真正的设计内容"。
# 例如："你刚才三句重复了。另外错层会不会太碎？"——前半是元反馈（评论 AI 行为），
# 后半是设计问题。元反馈不得修改设计状态（project/design_focus/student_decisions/
# issue_register/pending_clarification），但其中明确的设计指令（"不想做中庭""先看入口"）
# 仍必须生效。
#
# 判定：按标点切句，逐句判断"作用对象是 AI 行为/系统，还是设计内容"。
#   元反馈句特征：
#     - 主语是"你/系统/AI/上轮/刚才"，动词是 AI 行为（说/问/讲/重复/出bug/卡住/理解错/变来变去…）
#     - 或直接评论上轮输出本身（"那三句话重复了""这句什么意思"）
#   设计句特征（即使和元反馈相邻）：主语是"我"，或对象是设计事物（错层/儿童区/中庭/入口/布局…）
#     + 动词是设计动作（做/改/看/放/想/担心/觉得…）

# AI 行为动词：评论 Agent 输出/行为时出现
# 元反馈片段剥离（句子内部）："你刚才理解错了，先别聊儿童区" —— 剥离"你…理解错"前缀，保留设计指令
# 注意：不剥"你说的X/你说过X"（引用 AI 建议 = 设计内容），只剥质疑式（"你为什么说""你怎么说"）
_META_FRAGMENT_STRIP = re.compile(
    r"^(?:你|系统|AI)(?:为什么|怎么|老是|总是|刚才|之前|前面)?(?:一直|反复|又|老)?"
    r"(?:重复|叠|出bug|卡住|卡了|理解错|记错|说错|变来变去|自相矛盾|答非所问|"
    r"(?:为什么|怎么)?说(?:这个|那个|这样|这种)|在问|问(?:个|的|这个|那个)?(?:没完|个不停|好几))"
    r"[^，。！？；,;!?]*[，,、；;]?"
)

_META_VERBS = re.compile(
    r"出bug|出问题|卡住|卡了|重复|叠(?:了|在)|又说|又(?:问|说|讲)|为什么一直(?:说|问|讲|提|聊)|"
    r"为什么(?:你|老是|总是)|什么意思|什么(?:意思|情况)|是不是(?:错了|有问题|出问题)|理解错|"
    r"记错|说错|变来变去|自相矛盾|前后矛盾|答非所问|刚才.{0,6}(?:说|讲|回|答)|"
    r"这句|那句话|上一轮|上一句|上一条|你的回复|你的回答|你的开场|你开头|你前面|你刚才|你之前"
)

# 元反馈的强信号：评论 AI 行为/系统本身（含"你/系统"做主语 + 行为动词，或直接指称上轮输出）
_META_STRONG = re.compile(
    r"(?:你|系统|AI|机器人|它)(?:是|在)?(?:不是)?(?:出bug|卡住|卡了|重复|理解错|记错|说错|变来变去|自相矛盾)|"
    r"(?:刚才|前面|上一轮|上一句|上一条|那三句|那些话|你的开场|你开头)(?:的)?(?:话|句|回复|回答|输出)?(?:重复|叠|卡|错|矛盾|有(?:问题|bug))"
)

# 元反馈的"你主语 + AI行为动词"模式：优先级高于设计词
# （"你为什么一直讲中庭""你刚才理解错了""你怎么老是在问"——主语是你/AI，不是"我"）
# 注意："你说的X/你说过X"是引用 AI 的建议（设计内容），不是元反馈，必须排除。
_META_YOU_VERB = re.compile(
    r"你(?:为什么|怎么|老是|总是|又|刚才|之前|前面|倒是)?(?:一直|反复|又|老|还)?"
    r"(?:重复|叠|出bug|卡住|卡了|理解错|记错|说错|变来变去|自相矛盾|答非所问|"
    r"又(?:问|说|讲)|为什么一直(?:问|说|讲)|问(?:个|的|这个|那个)?(?:没完|个不停|好几))|"
    r"你(?:是不是|是否|有没有)?(?:出bug|卡住|卡了|重复|理解错|说错|记错)|"
    r"你(?:为什么|怎么)(?:说|问|讲|提)(?:这个|那个|中庭|儿童区|这样)|"
    r"你(?:为什么|怎么).{0,6}在问|你老是问|你怎么老(?:是|在)|你又问|你总是问"
)

# 设计内容强信号：主语是"我"（学生自己的设计指令/疑问）
_DESIGN_STRONG = re.compile(
    r"我(?:想|要|决定|选|不|不想|不要|改|换|放|看|做|觉得|担心)|"
    r"先(?:别|不)?(?:聊|看|想|做|谈)|"
    r"(?:错层|儿童区|阅览|自习|报告厅|活动室|中庭|入口|楼梯|庭院|布局|平面|剖面|采光|流线|面积|层数|功能)"
)

# 句切分（保留引号内整体）
_SENT_SPLIT = re.compile(r"(?<=[。！？；!?;])\s*")


def split_meta_feedback(message: str) -> tuple[list[str], str]:
    """把用户输入拆成（元反馈片段, 设计内容片段）。

    元反馈片段：评论 AI 行为/系统/上轮输出，不得修改设计状态。
    设计内容片段：照常进入语义事件/update_state/update_focus。
    支持混合意图：同一轮输入中两者可以并存，互不吞并，
    同一句内也可剥离元反馈前缀（"你刚才理解错了，先别聊儿童区"→meta="你刚才理解错了"+design="先别聊儿童区"）。
    段级判断：逗号连接的"你怎么老是在问儿童区，我自己还没想清楚两层还是三层"
    → meta="你怎么老是在问儿童区" + design="我自己还没想清楚两层还是三层"。
    """
    text = (message or "").strip()
    if not text:
        return [], ""
    sentences = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    meta_parts: list[str] = []
    design_parts: list[str] = []
    for sent in sentences:
        # 段切分只用中文逗号/顿号/分号——英文逗号是句内标点（"programming, boys"），不能切
        segments = [seg.strip() for seg in re.split(r"[，、；]", sent) if seg.strip()]
        if len(segments) <= 1:
            stripped, remainder = _strip_meta_prefix(sent)
            if stripped:
                meta_parts.append(stripped)
            if remainder:
                if _is_meta_sentence(remainder):
                    meta_parts.append(remainder)
                else:
                    design_parts.append(remainder)
        else:
            # 多段：逐段判断；元反馈段进 meta，其余段合并进 design
            for seg in segments:
                if _is_meta_sentence(seg):
                    meta_parts.append(seg)
                else:
                    design_parts.append(seg)
    # 没有元反馈时无需改写原句，保留字段声明与新答案之间的标点边界。
    return meta_parts, text if not meta_parts else "".join(design_parts)


def _strip_meta_prefix(sent: str) -> tuple[str, str]:
    """剥离句子开头的元反馈前缀片段（"你刚才理解错了，先别聊儿童区" → ("你刚才理解错了", "先别聊儿童区")）。

    仅当开头是"你/系统 + AI行为动词 + 短片段 + 逗号/顿号"时剥离；
    剥离后剩余部分按设计内容处理。不匹配则原句返回。
    """
    m = _META_FRAGMENT_STRIP.match(sent)
    if not m:
        return "", sent
    prefix = m.group(0).strip(" ，,、；;")
    remainder = sent[m.end():].strip(" ，,、；;")
    # 元反馈前缀要短（避免误剥"你为什么会觉得这个布局有问题"这类设计疑问）
    if len(prefix) > 18 or len(prefix) < 4:
        return "", sent
    return prefix, remainder


def _is_meta_sentence(sent: str) -> bool:
    """判断一句是元反馈（评论 AI 行为/系统）还是设计内容。"""
    # 优先级1：主语是"你"+ AI 行为动词 → 元反馈（无论是否含设计词）
    if _META_YOU_VERB.search(sent):
        return True
    # 优先级2：明确的设计指令/疑问（主语是"我"或"先别聊"等设计动作）→ 设计句
    if _DESIGN_STRONG.search(sent) and not _META_STRONG.search(sent):
        return False
    # 优先级3：评论系统/上轮输出的强信号 → 元反馈
    if _META_STRONG.search(sent):
        return True
    # 优先级4：AI 行为动词 + 主语是"你/系统/刚才/上一轮"
    if _META_VERBS.search(sent):
        if re.search(r"^(?:你|系统|AI|刚才|前面|上一轮|上一句|那句|那些)", sent):
            return True
    return False


def meta_feedback_context(meta_parts: list[str]) -> str:
    """把元反馈片段整理成给 LLM 的提示（要求先回应，不当作设计指令）。"""
    if not meta_parts:
        return ""
    return (
        "用户对你的行为/输出提出了以下反馈（这不是设计指令，不要据此修改方案状态，"
        "但要先诚实回应，如承认错误、澄清原因，然后继续处理其余设计内容）：\n"
        + "\n".join(f"- {p}" for p in meta_parts)
    )


def empty_state() -> dict:
    return {
        "project": {key: {} for key in PROJECT_FIELDS},
        "student_intent": [],
        "student_decisions": [],
        "ai_suggestions": [],
        "assumptions": [],
        "unresolved_questions": [],
        "conflicts": [],
        "knowledge_used": [],
        "source_records": [],
        "interaction_log": [],
        "ai_contributions": [],
        "question_history": [],
        "change_log": [],
        "versions": [],
        "current_stage": "探索",
        "pending_clarification": "",
        "collaboration_focus": empty_focus(),
        # V2：框架归属轨迹——设计方向最初由谁提出（防"隐形路线"洗白）
        # 条目：{text, origin: "ai_suggestion"|"student", turn_id, status: "proposed"|"confirmed"|"weak_ack"}
        "framework_trail": [],
        # V0.2 设计思考控制层（方案：01_项目规划/.../筑思Agent_设计思考控制层_V0.1_方案.md）
        # 当前主线——"现在在研究什么"，必须由学生确认进入
        "design_focus": {
            "topic": "",
            "confirmed_by": "",          # "student"（或 student 明确接受的 ai 提议）
            "turn_id": 0,
            "history": [],               # 主线变更记录（路线回滚依据）
        },
        # 议题库——所有被提出过的议题及状态
        # 状态机：proposed → candidate → active；optional(备选)/rejected(否定)/dormant(旧主线)
        "issue_register": {},
        # 已拒绝假设——学生明确否定的前提；status=forbidden 注入上下文最高优先级
        "rejected_assumptions": [],
        # V0.2.1 图纸事实真值层：学生对图纸的明确纠正，覆盖视觉原始识别
        # 条目：{statement, source: "student_correction", overrides: "vision_detection",
        #        confidence: "confirmed", turn_id}
        "drawing_facts": [],
        # V1.2 语义事件层：统一协议 semantic_event
        #   {type, target_id, payload, source, confidence, status, turn_id, raw}
        #   type: select | revise | correct | refocus | confirm | weak_ack | supplement | request_output
        #   target_id: 作用对象（choice_set_id / issue_id / fact_id / focus_topic）
        #   status: applied（已生效）| revoked（被推翻/改选后作废）| superseded（被新事件覆盖）
        # 事件追加写、不删除——可追溯性来源；UI 用 status 区分"当前有效"与"历史"。
        "semantic_events": [],
        # AI 上一轮提出的可选对象集（choice set）——学生下一轮的 select/revise 作用对象
        #   {id, question, options: [{id, label}], turn_id, status: "open"|"consumed"}
        "pending_choice": {},
        # 学生已选方向（语义事件 select/revise 的产物）
        #   {choice_set_id, option_id, label, source: "student", status: "active"|"revoked", turn_id}
        "selected_options": [],
        # AI/视觉提出的事实候选（可被 correct 事件作用；拥有稳定 ID，不裸存自然语言）
        #   {id, statement, origin: "ai"|"vision", status: "candidate"|"confirmed"|"superseded"}
        "fact_candidates": [],
        # V1.2 设计产出进度：跟踪"设计走到哪个粒度"，供 delegation/推进判断使用
        #   levels: ["function_relations", "space_organization", ...] 已产出的粒度（去重，保序）
        #   current: 最近一轮产出的粒度
        #   粒度序（推进方向）：function_list → function_relations → space_organization
        #     → placement（落位）→ circulation（垂直交通/流线）→ scale（尺度面积）→ detail（局部深化）
        "design_progress": {
            "levels": [],
            "current": "",
        },
    }


# ── 图纸事实真值层（学生对图纸的纠正 > 视觉原始识别）──────────────────────

# 图纸事实纠正信号（V1.2 语义结构重写）：
# correction 必须同时满足：
#   1. 存在被纠正对象（图面要素词 或 数值）
#   2. 存在"否定/替换/更正"语义（不是/其实是/看错了/不对/应该是/没有X/改回…）
#   3. 不是疑问句（"有没有问题/怎么办/合理吗/怎么样/为什么"是提问，不是纠正）
# 不再用"出现图面词 → correction"的宽词表（会把"流线有没有问题？"误判成纠正）。
_DRAWING_ELEMENT_WORDS = (
    "楼梯", "窗", "窗户", "门", "墙", "走廊", "走廊", "房间", "卧室", "客厅", "厨房", "餐厅",
    "卫生间", "车库", "庭院", "院子", "水池", "阳台", "露台", "阁楼", "地下室", "入口", "门厅",
    "中庭", "天井", "一层", "二层", "楼上", "楼下", "上层", "下层", "层",
)

# 强否定/替换/更正语义（区别于"有没有"这种疑问用法）
_DRAWING_CORRECT_RE = re.compile(
    r"(?:不是|根本不是|哪是|其实是|其实有|应该是|应该是|看错了|看错|搞错|"
    r"说错|记错|写错|标错|画错|错了|不对|没有窗|没有门|没有楼梯|没有这个|"
    r"不存在|没有(?:那个|这个|什么)|改回|改过来|纠正一下|更正|重新标)"
)

# 疑问句信号：含这些词 → 是提问/判断请求，不是图纸纠正
_DRAWING_QUESTION_RE = re.compile(
    r"[？?]|有没有问题|有问题吗|怎么办|合理吗|合不合理|怎么样|为什么|"
    r"能不能|会不会|该不该|要不要|是不是(?:问题|合理)|怎么改|怎么调整|行不行"
)

# 数值更正信号："14000 不对，是 14500" / "刚才说的尺寸错了"
_DRAWING_NUM_RE = re.compile(r"\d{3,6}|数字|尺寸|标注|数值")


def _active_vision_facts(updated: dict) -> list[dict]:
    """当前可指向的有效视觉事实（active vision evidence）。

    只含 origin=vision 且未被 superseded 的事实候选；
    student 提供的事实（source=student）不属于视觉事实，不能被"覆盖"。
    """
    result = []
    for cand in updated.get("fact_candidates", []):
        if cand.get("origin") == "vision" and cand.get("status") not in ("superseded", "revoked"):
            result.append(cand)
    # 兼容旧 drawing_facts 里 origin=vision 的记录
    for f in updated.get("drawing_facts", []):
        if f.get("origin") == "vision" and f.get("status") != "superseded":
            result.append(f)
    return result


def register_vision_facts(updated: dict, vision_items: list[dict], turn_id: int) -> None:
    """注册视觉模型产生的事实候选（origin=vision，带稳定 id）。

    不变量基础：只有先注册的视觉事实，才可能被后续学生纠正所"覆盖"。
    vision_items: [{"statement": "这里是楼梯", "element": "楼梯", "location": "车库西侧", ...}]
    """
    if not vision_items:
        return
    candidates = updated.setdefault("fact_candidates", [])
    for i, item in enumerate(vision_items):
        statement = str(item.get("statement") or item.get("value") or "").strip()[:200]
        if not statement:
            continue
        if any(c.get("origin") == "vision" and c.get("statement") == statement for c in candidates):
            continue  # 同一原始陈述重传不能恢复已被纠正的候选。
        fid = f"vision-{turn_id}-{i}"
        candidates.append({
            "id": fid,
            "statement": statement,
            "element": str(item.get("element", ""))[:40],
            "location": str(item.get("location", ""))[:60],
            "origin": "vision",
            "source": "vision",
            "status": "candidate",
            "turn_id": turn_id,
        })
    updated["fact_candidates"] = candidates[-100:]


def record_drawing_fact(updated: dict, statement: str, turn_id: int) -> None:
    """记录学生关于图纸/空间的陈述。

    视觉覆盖不变量（V1.2）：
      - 只有存在**可指向的有效视觉事实**（origin=vision 的 active fact_candidate/drawing_fact），
        且学生陈述与该视觉事实同主题时，才产生 overrides（并指向具体 vision_fact_id）；
      - 没有可指向视觉事实时，记录为 student 提供的图纸事实（source=student），
        **永不产生 overrides: vision_detection**——不存在的证据不能被覆盖。
    学生改口（"好像确实是楼梯"）时：作废同主题旧事实（标 superseded），以新陈述为准。
    """
    statement = str(statement).strip()[:200]
    if not statement:
        return
    facts = updated.setdefault("drawing_facts", [])
    # 同主题判定：新陈述与旧陈述包含同一图面要素词（楼梯/窗/门/车库…）
    new_kw = _fact_keywords(statement)
    identity = _contrastive_identity(statement)
    for f in facts:
        if f.get("statement") == statement:
            f["turn_id"] = turn_id
            return
    for f in facts:
        if f.get("status") == "superseded":
            continue
        old_kw = _fact_keywords(f.get("statement", ""))
        conflicts = (_matches_rejected_identity(f.get("statement", ""), identity)
                     if identity else bool(new_kw & old_kw and _DRAWING_CORRECT_RE.search(statement)))
        if conflicts:
            f["status"] = "superseded"
            f["superseded_by"] = statement
    # 视觉覆盖不变量：找可指向的同主题视觉事实
    vision_target = None
    for vf in _active_vision_facts(updated):
        vf_kw = _fact_keywords(vf.get("statement", ""))
        matches = (_matches_rejected_identity(vf.get("statement", ""), identity)
                   if identity else bool(new_kw & vf_kw))
        if matches:
            vision_target = vision_target or vf.get("id") or "vision_unknown"
            if identity:
                vf["status"] = "superseded"
                vf["superseded_by"] = statement
            else:
                break
    if vision_target:
        facts.append({
            "statement": statement,
            "source": "student_correction",
            "overrides": vision_target,  # 指向具体视觉事实，不锅端
            "confidence": "confirmed",
            "turn_id": turn_id,
        })
    else:
        # 无视觉事实可覆盖 → 仅记录学生提供的图纸事实，不产生 visual override
        facts.append({
            "statement": statement,
            "source": "student",
            "confidence": "confirmed",
            "turn_id": turn_id,
        })
    updated["drawing_facts"] = facts[-30:]


_FACT_KEYWORDS = ("楼梯", "窗", "门", "墙", "车库", "庭院", "厨房", "餐厅", "客厅", "卧室", "主卧", "次卧", "老人房", "客房", "卫生间", "水池", "阳台", "露台", "走廊", "入口", "一层", "二层", "楼上", "楼下")


def _fact_keywords(text: str) -> set[str]:
    return {w for w in _FACT_KEYWORDS if w in str(text)}


def _contrastive_identity(message: str) -> tuple[str, str, str] | None:
    """明确的 X不是Y，Z才是（Y），不依赖地名或建筑要素词表。"""
    text = str(message).strip().rstrip("。.")
    if re.search(r"[？?]|吗|可能|也许|好像|似乎|不确定|是不是", text):
        return None
    match = re.fullmatch(r"([^，,；;。]{1,60}?)不是([^，,；;。]{1,60})[，,；;]\s*([^，,；;。]{1,60}?)才是(.*)", text)
    if not match:
        return None
    old, identity, new, repeated = (part.strip() for part in match.groups())
    if repeated and repeated != identity:
        return None
    return old, identity, new


def _matches_rejected_identity(statement: str, parts: tuple[str, str, str]) -> bool:
    old, identity, _new = parts
    text = re.sub(r"\s+", "", str(statement)).strip("。.")
    old, identity = re.escape(old), re.escape(identity)
    return bool(re.fullmatch(rf"{old}(?:是|为|有){identity}|{identity}(?:在|位于){old}", text))


def detect_drawing_correction(message: str) -> str | None:
    """检测学生是否在纠正图面要素/数值（"车库西侧不是楼梯"）→ 返回提取的 statement。

    语义结构（V1.2 重写）：correction = 被纠正对象 + 否定/替换语义 + 非疑问句。
      - 对象：图面要素词（楼梯/窗/门/庭院…）或数值（14000/尺寸标注）
      - 否定/替换：不是/其实是/看错了/不对/应该是/没有X/改回…
      - 排除：疑问句（"流线有没有问题？""楼梯放这里合理吗？"）——提问不是纠正。

    区别于议题否定（reject_issue）：这里纠正的是"图面是什么"（图纸事实），
    不是"研究什么"（议题）。
    """
    msg = (message or "").strip()
    if not msg:
        return None
    # 1) 疑问句 → 不是纠正（提问/判断请求）
    if _DRAWING_QUESTION_RE.search(msg):
        return None
    if _contrastive_identity(msg):
        return msg.strip(" ，。！？!?")[:200]
    # 2) 必须有被纠正对象：图面要素词 或 数值
    has_element = any(w in msg for w in _DRAWING_ELEMENT_WORDS)
    has_number = bool(_DRAWING_NUM_RE.search(msg))
    if not (has_element or has_number):
        return None
    # 3) 必须有否定/替换/更正语义
    if not _DRAWING_CORRECT_RE.search(msg):
        return None
    # 提取纠正内容：把消息清洗成"X不是Y / X其实是Z / X改回W"的陈述
    statement = msg.strip(" ，。！？!?")
    statement = re.sub(r"^(?:我(?:跟|对)?你?说|你(?:给|帮)?我(?:记|注意)|老师|等等|等一下|你看|你听|更正|纠正|改一下)\s*", "", statement)
    statement = re.sub(r"[。！？!?；;]+$", "", statement).strip()
    if len(statement) >= 4:
        return statement[:200]
    return None


# ── V0.2 设计思考控制层：状态操作（确定性，非 LLM 生成）────────────────────

_ISSUE_STATUSES = ("proposed", "candidate", "active", "optional", "rejected", "dormant")


def record_issue(updated: dict, text: str, origin: str, turn_id: int,
                 status: str = "proposed", evidence: str = "") -> str:
    """写入一个议题（AI 提议或学生提出）。

    Args:
        origin: "ai" | "student"
        status: 见 _ISSUE_STATUSES；AI 提议默认 proposed，学生提出可 candidate。
    Returns:
        issue_id
    """
    if status not in _ISSUE_STATUSES:
        status = "proposed"
    reg = updated.setdefault("issue_register", {})
    issue_id = f"issue-{turn_id}-{len(reg) + 1}"
    reg[issue_id] = {
        "text": str(text)[:200], "origin": origin, "status": status,
        "proposed_turn": turn_id, "confirmed_turn": None,
        "evidence": str(evidence)[:300],
    }
    updated["issue_register"] = dict(list(reg.items())[-40:])
    return issue_id


def update_issue_status(updated: dict, issue_id: str, status: str, turn_id: int) -> bool:
    """议题状态转移（proposed→candidate→active；→optional/rejected/dormant）。"""
    reg = updated.get("issue_register", {})
    issue = reg.get(issue_id)
    if not issue or status not in _ISSUE_STATUSES:
        return False
    issue["status"] = status
    if status == "active":
        issue["confirmed_turn"] = turn_id
    return True


def reject_assumption(updated: dict, text: str, turn_id: int) -> None:
    """记录学生明确否定的假设/前提（status=forbidden）。

    forbidden 条目注入上下文最高优先级，防止 AI 几轮后重新提出该议题。
    """
    rejected = updated.setdefault("rejected_assumptions", [])
    normalized = str(text)[:200].strip()
    if not normalized:
        return
    for item in rejected:
        if item.get("text") == normalized:
            return
    rejected.append({"text": normalized, "status": "forbidden", "turn_id": turn_id})
    updated["rejected_assumptions"] = rejected[-30:]


def set_design_focus(updated: dict, topic: str, turn_id: int, confirmed_by: str = "student") -> None:
    """切换当前主线：旧主线降级 dormant，新主线生效。"""
    focus = updated.setdefault("design_focus", {})
    old_topic = focus.get("topic", "")
    if old_topic and old_topic != topic:
        focus.setdefault("history", []).append({
            "topic": old_topic, "status": "dormant", "turn_id": turn_id,
        })
        # 旧主线对应议题降级
        for issue_id, issue in updated.get("issue_register", {}).items():
            if issue.get("text") == old_topic and issue.get("status") in ("active", "candidate"):
                issue["status"] = "dormant"
    focus["topic"] = str(topic)[:200]
    focus["confirmed_by"] = confirmed_by
    focus["turn_id"] = turn_id
    focus["history"] = focus.get("history", [])[-20:]


def record_framework(updated: dict, text: str, origin: str, turn_id: int, status: str = "proposed") -> None:
    """记录一个设计方向/框架的来源归属。

    硬规则：origin="ai_suggestion" 的条目，即使学生回复"嗯/可以/继续"
    （weak_ack），也**不升级**为 student_decision——只有学生明确
    "我决定/我选择/就用/确定采用"才进入 student_decisions。
    """
    trail = updated.setdefault("framework_trail", [])
    trail.append({
        "text": str(text)[:200], "origin": origin, "turn_id": turn_id, "status": status,
    })
    updated["framework_trail"] = trail[-60:]


def _fact(value: str, evidence: str, turn_id: int, status: str = "confirmed") -> dict:
    return {
        "value": value.strip(), "status": status, "source": "student",
        "evidence": evidence.strip(), "turn_id": turn_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _project_type(text: str) -> str:
    types = re.findall(
        r"大学生活动中心|大学生活中心|学生活动中心|乡村独立住宅|公共博物馆|社区图书馆|社区文化中心|住宅|民宿|写字楼|办公楼|学校|小学|中学|大学|幼儿园|博物馆|美术馆|展览馆|展馆|广场|文化馆|图书馆|体育馆|酒店|医院",
        text,
    )
    return types[-1] if types else ""


_PREVIOUS_REFERENCE_RE = re.compile(
    r"上一(?:个问题|题)|刚才(?:那个|的|说的|说)|前面(?:那个|说的|提到)|"
    r"我(?:刚才|前面|之前).{0,6}(?:说的|提到的|决定)"
)
_EXPLICIT_REVISION_ACTION_RE = re.compile(
    r"修改|改一下|调整一下|改为|改成|改到|改放|换成|挪(?:到|向|去)|还是放"
)
_REFERENCED_CORRECTION_RE = re.compile(r"应该是|不是.+?是|放(?:在|到)")
_REVISION_AFFORDANCE_RE = re.compile(
    r"(?:能|可以|可|允许)(?:被)?修改(?!为|成|到|放|一下).{0,16}(?:骨架|方案|方向|草案|结果)|"
    r"(?:骨架|方案|方向|草案|结果).{0,16}(?:能|可以|可|允许)(?:被)?修改(?!为|成|到|放|一下)"
)


def is_previous_answer_revision(text: str) -> bool:
    """区分真正修改上文与仅沿上文继续推进。"""
    value = text or ""
    action_scope = _REVISION_AFFORDANCE_RE.sub("", value)
    return bool(
        _EXPLICIT_REVISION_ACTION_RE.search(action_scope)
        or (_PREVIOUS_REFERENCE_RE.search(value) and _REFERENCED_CORRECTION_RE.search(value))
    )


def _replace_previous(state: dict, text: str, turn_id: int) -> bool:
    if not is_previous_answer_revision(text):
        return False
    all_history = [item for item in state.get("question_history", []) if item.get("dimension") in PROJECT_FIELDS]
    # 显式字段 + 后续完整陈述，也是在提供新答案，不要求学生使用“改为”。
    # 只识别已有项目字段；未知范围和疑问仍交给原澄清路径。
    clauses = re.split(r"[，,；;。]\s*", text, maxsplit=1)
    stated_dimension = ""
    stated_value = ""
    if len(clauses) == 2:
        field_patterns = (("users", r"使用者|服务对象|人群"), ("site", r"场地|基地"),
                          ("scale", r"面积|规模"), ("functions", r"功能"),
                          ("goals", r"目标"), ("constraints", r"限制|预算"))
        dimensions = [key for key, pattern in field_patterns if re.search(pattern, clauses[0])]
        assertion = clauses[1].strip(" ，。；,;")
        if (len(dimensions) == 1 and re.search(r"\S.{0,50}是\S.{1,80}$", assertion)
                and not re.search(r"[？?]|(?:是否|是不是|可能|也许|好像|不确定|不知道)|(?:吗|呢)$", assertion)):
            stated_dimension, stated_value = dimensions[0], assertion
    match = re.search(r"(?:修改为|改为|改成|换成|应该是|不是.+?是|放(?:在|到)|挪(?:到|向|去)|改(?:到|成|为|放)|还是放)\s*([^，。；,;]{2,40})", text)
    if not match and not stated_value:
        state["pending_clarification"] = "你想修改前面的哪一项？请同时告诉我新的答案。"
        return True
    value = stated_value or match.group(1).strip(" ，。；,;")
    semantic_rules = (
        ("users", r"面向|群体|使用者|服务对象"), ("site", r"场地|基地|位于|河边|山地"),
        ("scale", r"面积|规模|平方米|平米|㎡"), ("functions", r"功能|活动|展陈|办公|会议"),
        ("goals", r"目标|希望|体验"), ("constraints", r"限制|预算|保留|工期"),
    )
    semantic_dimension = next((key for key, pattern in semantic_rules if re.search(pattern, value)), "")
    answered = [item for item in all_history if item.get("answer")]
    fallback_dimension = (answered or all_history)[-1]["dimension"] if (answered or all_history) else ""
    dimension = stated_dimension or semantic_dimension or fallback_dimension
    if not dimension:
        state["pending_clarification"] = "你想修改前面的哪一项？可以直接说使用者、场地、功能或其他具体内容。"
        return True
    old = state["project"].get(dimension, {}).get("value", "")
    state["project"][dimension] = _fact(value, text, turn_id)
    matching = next((item for item in reversed(all_history) if item.get("dimension") == dimension and item.get("answer")), None)
    if matching:
        matching["answer"] = value
    state["change_log"].append({"dimension": dimension, "from": old, "to": value, "turn_id": turn_id})
    state["pending_clarification"] = ""
    return True


def update_state(state: dict | None, text: str, turn_id: int = 0) -> dict:
    updated = deepcopy(state or empty_state())
    updated.setdefault("project", {key: {} for key in PROJECT_FIELDS})
    for key in PROJECT_FIELDS:
        updated["project"].setdefault(key, {})
    updated.setdefault("change_log", [])
    updated.setdefault("question_history", [])
    # 澄清文字是当前轮的处理结果，不能作为下一轮的结论直接继承。
    # 本轮仍不明确的撤销或修改会在下方重新产生澄清；原对话历史保留。
    updated["pending_clarification"] = ""
    updated.setdefault("source_records", [])
    updated.setdefault("interaction_log", [])
    updated.setdefault("ai_contributions", [])

    # 撤销/反悔（V1.1 修复：区分"反悔"与"转换话题"）
    # 触发条件：明确的反悔表达。"算了"只有后跟反悔词才算撤销，
    # "算了先看功能吧"（转换话题）不算。
    retract_text = retraction_signal_text(text)
    retract_trigger = re.search(
        r"撤销|取消刚才|先不确定|不算|不作数|当没说过|当我没说|别搞那么复杂|不要了|不要做|不做了|"
        r"不想(?:做|用|要)|不要(?:这个|那个|它|中庭|入口)|改(?:回|掉|掉重来)|推翻|收回",
        retract_text,
    )
    # "算了"仅在后面跟明确反悔意图时触发；否则视为转换话题
    suanle_retract = re.search(r"算了[，,、]?\s*(?:撤销|不算|不要|不做|取消|当没说过|别搞|推翻)", retract_text)
    # 拒绝一个仍处于候选状态的方向，不等于撤销任何已确认决定。
    # 例如“不要双入口这个候选”不能因为都含“入口”就删除“东侧单入口”的确认记录。
    candidate_rejection = re.search(
        r"(?:不想要|不要了?|放弃|取消|撤销|收回)[^。；;]{0,30}候选|"
        r"候选[^。；;]{0,20}(?:不要了?|放弃|取消|撤销|收回)",
        retract_text,
    )
    decided = updated.get("student_decisions", [])
    candidate_route_rejection = bool(
        not decided
        and re.search(
            r"(?:收回|收回来|撤销|取消|放弃|放掉|停止|不要|不采用|不继续).{0,24}(?:方向|路线|方案|组织|分法|骨架)|"
            r"(?:方向|路线|方案|组织|分法|骨架).{0,16}(?:收回|收回来|撤销|取消|放弃|放掉|停止|不要|不采用|不继续)|"
            r"(?:不想用|不想要|不要|放弃)[^。；;]{0,16}"
            r"(?:大厅|中庭|庭院|院子|街道|走廊|主轴|中心)"
            r"[^。；;]{0,12}(?:当|作为|做|组织|心脏|核心)?",
            retract_text,
        )
    )
    if candidate_rejection or candidate_route_rejection:
        retract_trigger = None
        suanle_retract = None
    if retract_trigger or suanle_retract:
        # V1.2 语义结构修复：撤销词"出现"不等于"学生在撤销"。
        # "收回"可能出现在复述/引用上下文（"那是你上一轮说的'我收回…'，我在复述你"），
        # 或质疑他人表述（"你怎么说收回就收回"）——这些不是学生对自己的决定反悔。
        # 判定：撤销意图需要 ① 第一人称反悔动词（我收回/我撤销/我不算…）或 ② 明确针对已有对象
        #   且 ③ 消息里确实存在可撤销的设计决定/项目字段。
        _first_person_retract = re.search(
            r"我(?:收回|撤销|取消|不算|不作数|推翻|不要了|不做了)|"
            r"(?:刚才|之前|前面).{0,8}(?:不算|不要|取消|撤销)|"
            r"算了.{0,4}(?:不要|不做|不算)",
            retract_text,
        )
        # 转述结构优先判定："你上一轮自己说的我收回…""你说我收回"——"我收回"是引用对方的话，
        # 不是本人反悔（即使字面含"我收回"也不触发）
        if re.search(r"你(?:上|刚才|之前)?.{0,8}(?:说|讲)(?:的)?我收回|你说我收回|你(?:自己)?说我收回|复述.{0,4}我收回|引用.{0,4}我收回", text):
            retract_trigger = None
            suanle_retract = None
        has_retractable_object = bool(
            decided
            or any(updated["project"].get(dim, {}).get("value") for dim in PROJECT_FIELDS)
        )
        # 没有任何可撤销对象 → 不是撤销场景（可能只是复述/质疑）
        if not has_retractable_object:
            retract_trigger = None
            suanle_retract = None
        # 有对象但缺第一人称反悔动词 → 先看是否"复述/引用/质疑"
        elif not _first_person_retract:
            # 质疑/反问结构："你怎么说收回就收回"——质疑对方行为，不是自己反悔
            if re.search(r"怎么.{0,4}(?:说|就).{0,4}(?:收回|撤销|不算)|凭什么|为什么.{0,4}(?:收回|撤销)", text):
                retract_trigger = None
                suanle_retract = None
            # 复述/引用（引号包裹的"我收回"、转述）
            quoted_retract = re.search(r"['\"“”‘’]?(?:我)?收回['\"“”‘’]?", text)
            if quoted_retract and re.search(r"复述|引用|你(?:上|刚才)?说|你说过|你(?:自己)?说的|质疑|你说收回", text):
                retract_trigger = None
                suanle_retract = None
    if retract_trigger or suanle_retract:
        # 1) 设计决策撤销：识别"中庭/入口/大厅/水吧/庭院"等设计决策词
        design_decision_terms = ("中庭", "入口", "大厅", "水吧", "庭院", "咖啡", "阅览区", "儿童区", "主入口")
        decided = updated.get("student_decisions", [])
        # 找到匹配的设计决定并撤销
        target = next((d for d in reversed(decided) if any(t in str(d.get("value", "")) for t in design_decision_terms)), None)
        if target:
            # 只撤销这一个设计决定，项目上下文（类型/场地/规模）保持不变
            updated["student_decisions"] = [d for d in decided if d is not target]
            updated["change_log"].append({
                "dimension": "design_decision", "from": target.get("value", ""), "to": "",
                "type": "retracted", "turn_id": turn_id, "evidence": text,
            })
            updated["pending_clarification"] = ""
            return updated
        # 2) 基本信息维度撤销（7 个维度）
        dimension_rules = (
            ("users", r"使用者|人群|群体"), ("site", r"场地|基地"), ("scale", r"面积|规模"),
            ("functions", r"功能|活动"), ("goals", r"目标|体验"), ("constraints", r"限制|预算"),
            ("project_type", r"项目类型|建筑类型"),
        )
        dimension = next((key for key, pattern in dimension_rules if re.search(pattern, text)), "")
        if not dimension:
            answered = [item for item in updated.get("question_history", []) if item.get("answer")]
            dimension = answered[-1]["dimension"] if answered else ""
        if dimension and updated["project"].get(dimension):
            old = updated["project"][dimension].get("value", "")
            updated["project"][dimension] = {}
            updated["change_log"].append({"dimension": dimension, "from": old, "to": "", "type": "retracted", "turn_id": turn_id})
            return updated
        # 3) 反悔但不清楚撤销什么：先看最近的学生决定
        if decided:
            last = decided[-1]
            updated["student_decisions"] = decided[:-1]
            updated["change_log"].append({
                "dimension": "design_decision", "from": last.get("value", ""), "to": "",
                "type": "retracted", "turn_id": turn_id, "evidence": text,
            })
            updated["pending_clarification"] = ""
            return updated
        updated["pending_clarification"] = "你想撤销哪一项决定？可以直接说项目类型、使用者、场地、功能，或者中庭、入口这类具体设计决定。"
        return updated

    if _replace_previous(updated, text, turn_id):
        return updated

    project_type = _project_type(text)
    if project_type:
        old = updated["project"]["project_type"].get("value", "")
        if old and old != project_type and re.search(r"改成|改为|不想做|换成|不是", text):
            updated["change_log"].append({"dimension": "project_type", "from": old, "to": project_type, "turn_id": turn_id})
        updated["project"]["project_type"] = _fact(project_type, text, turn_id)

    site_assertion = _extract_site_assertion(text)
    if site_assertion:
        value, evidence = site_assertion
        updated["project"]["site"] = _fact(value, evidence, turn_id)

    rules = {
        "users": r"(?:面向|服务于|使用者(?:是|为)?)\s*([^，。；,;]{2,40})",
        "scale": r"(\d+(?:\.\d+)?\s*(?:平方米|平米|㎡))",
    }
    for dimension, pattern in rules.items():
        match = re.search(pattern, text)
        if match:
            updated["project"][dimension] = _fact(match.group(1).strip(), match.group(0), turn_id)

    # 所有功能写入口共用同一提取规则。
    function_value = _extract_function_value(text)
    if function_value and not updated["project"]["functions"].get("value"):
        updated["project"]["functions"] = _fact(function_value, text, turn_id)

    if re.search(r"我决定|我选择|就用|确定采用|保留这个", text):
        updated.setdefault("student_decisions", []).append({"value": text, "turn_id": turn_id, "source": "student"})
    if re.search(r"我的想法|我希望|我想让|设计意图", text):
        updated.setdefault("student_intent", []).append({"value": text, "turn_id": turn_id, "source": "student"})
    return updated


def _extract_site_assertion(text: str) -> tuple[str, str] | None:
    """普通场地写入需要陈述关系；回问和无新事实的提醒不能覆盖记忆。"""
    for clause in re.split(r"[，,。；;！!\n]", text):
        if (_DRAWING_QUESTION_RE.search(clause) or re.search(
                r"吗|呢|哪里|哪儿|哪个|什么|怎么|是否|是不是|还是|有没有|"
                r"可能|也许|好像|似乎|不确定", clause)):
            continue
        match = re.search(
            r"(?:场地|基地)(?:(?:在|位于|是|为|选择|[:：])\s*([^，。；,;]{2,60})|"
            r"([^，。；,;]{1,20}(?:是|有|临|靠|接)[^，。；,;]{1,40}))", clause)
        if match:
            return (match.group(1) or match.group(2)).strip(), match.group(0).strip()
    return None


def _extract_function_value(text: str) -> str:
    """复用原有功能提取规则，供普通陈述和待回答问题共同使用。"""
    function_terms = (
        "阅览区|阅览|阅读区|自习室|自习区|儿童区|活动室|活动区|咖啡角|展厅|展览|办公室|办公区|"
        "报告厅|小剧场|手工区|游戏区|书库|中庭|共享大厅|门厅|剧场|教室|会议室|健身房"
    )
    funcs = list(dict.fromkeys(re.findall(function_terms, text)))[:6]
    if not funcs:
        return ""
    relation = ""
    if re.search(r"吵|热闹|活跃", text) and re.search(r"安静|静", text):
        relation = "存在动静分区关系"
    elif re.search(r"吵|热闹|活跃", text):
        relation = "部分功能较吵"
    return "、".join(funcs) + (f"（{relation}）" if relation else "")


def record_ai_question(state: dict, question: str, dimension: str, turn_id: int) -> dict:
    updated = deepcopy(state)
    if question and dimension in PROJECT_FIELDS:
        updated.setdefault("question_history", []).append({
            "question": question, "dimension": dimension, "answer": "", "turn_id": turn_id,
        })
    return updated


def answer_pending_question(state: dict, answer: str, turn_id: int) -> dict:
    """把用户对 AI 问题的回答写入对应维度。

    只在消息是"简短、明确的回答"时采纳，避免把功能清单、深化请求、
    疑问句、决定句等误当成对上一个问题的回答而污染 project 字段。
    判定条件（全部满足才算回答）：
      1. 长度 ≤ 40 字；
      2. 不含疑问词（？/吗/呢/是不是/应该放哪/怎么/为什么）；
      3. 不含请求/指令词（帮我/请/分析/深化/看看/画/上传/评图）；
      4. 不含"决定/我选/就用"（决定走 student_decisions）；
      5. 含回答性信号（是/要/放/用/朝向/面向/偏/大概/约/平米/东/西/南/北/学生/老人/儿童/居民 等）。
    """
    updated = deepcopy(state)
    history = updated.get("question_history", [])
    pending = next((item for item in reversed(history) if not item.get("answer") and item.get("dimension") in PROJECT_FIELDS), None)
    if not pending:
        return updated
    text = answer.strip()
    if not text or len(text) > 40:
        return updated
    if re.search(r"[？?]|吗|呢|是不是|应该放|怎么|为什么|哪个|还是|我不知道|不清楚|还没想好|不确定|没想好", text):
        return updated  # 疑问句/不确定表达不是回答
    if re.search(r"帮我|请|分析|深化|看看|画|上传|评图|梳理|建议", text):
        return updated  # 请求/指令不是回答
    if pending["dimension"] == "functions":
        if re.search(r"我决定|我选择|就用|确定采用", text):
            return updated
        value = _extract_function_value(text)
        if value:
            pending["answer"] = answer
            updated["project"]["functions"] = _fact(value, answer, turn_id)
        return updated
    if pending["dimension"] == "site":
        # 「是」只能表明这是陈述，不能证明它回答了场地问题。
        # 简短地点回答应带有空间落点；任务类型和对既有条件的提醒不应覆盖场地。
        if not re.search(r"(?:边|侧|内|外|部|区|地|址|园|院|路|街|山|河|前|后|旁|面)$", text):
            return updated
        pending["answer"] = answer
        updated["project"]["site"] = _fact(answer, answer, turn_id)
        return updated
    if re.search(r"功能(?:上|包括|有|是)|阅览区|儿童区|活动室|咖啡角|展厅|自习|报告厅", text):
        return updated  # 功能清单陈述交给 functions 抽取，不是对问题的回答
    if re.search(r"我决定|我选择|就用|确定采用", text):
        return updated  # 决定走 student_decisions 分支
    if not re.search(r"就|是|可以|应该|要|放|用|面向|朝着|朝向|偏(?:向|好)?|倾向|大概|约|平方米|平米|㎡|东|西|南|北|学生|老人|儿童|居民|开放|安静|热闹", text):
        return updated  # 没有回答性信号，交给正常信息抽取
    dimension = pending["dimension"]
    pending["answer"] = answer
    updated["project"][dimension] = _fact(answer, answer, turn_id)
    return updated


def create_version(state: dict, content: str, turn_id: int) -> dict:
    updated = deepcopy(state)
    number = len(updated.get("versions", [])) + 1
    record = {
        "number": number, "content": content, "turn_id": turn_id,
        "student_decisions": deepcopy(updated.get("student_decisions", [])),
        "knowledge_used": deepcopy(updated.get("knowledge_used", [])),
        "unresolved_questions": deepcopy(updated.get("unresolved_questions", [])),
    }
    updated.setdefault("versions", []).append(record)
    updated["current_stage"] = "阶段成果"
    return updated


# ══════════════════════════════════════════════════════════════════════
# V1.2 语义事件层（semantic event protocol）
#
# 原则：
#   1. 状态层存"语义事件"（学生选择了「知识仓库」），不存"用户原句"（user said "2"）；
#      原句保留在 event.raw 作证据。
#   2. 事件必须作用于明确的结构化对象（target_id：choice_set_id / issue_id / fact_id）。
#   3. 事件追加写、不删除；推翻 = 旧事件标 revoked / superseded，新事件写入。
#   4. 本层只做确定性状态操作（正则/枚举解析），不依赖 LLM 猜。
# ══════════════════════════════════════════════════════════════════════

_EVENT_TYPES = ("select", "revise", "correct", "refocus", "confirm", "weak_ack", "supplement", "request_output", "delegation")


# ── 设计产出记录（V1.2 记忆，非流水线）────────────────────────────
# 注意：这里是"已经做过什么"的记忆标签，不是"下一步必须做什么"的顺序。
# 建筑设计不是升级打怪：功能关系之后最该看的可能是场地（而非落位）；
# 平面刚出时最关键的可能是剖面；学生突然发现入口有问题就应该回头。
# 下一步推进什么，由 AI 重新扫描整体后判断（见 DESIGN_LANDSCAPE），不由本序列决定。
DESIGN_LEVELS = (
    ("function_list", "功能清单", "列出主要功能"),
    ("function_relations", "功能关系", "哪些功能靠近/隔开"),
    ("space_organization", "空间组织骨架", "整体分区、核心空间、动线骨架"),
    ("placement", "落位", "入口/公共区/阅览等如何围绕核心落位"),
    ("circulation", "垂直交通与流线", "楼梯/走廊/环廊如何连接各层"),
    ("scale", "尺度与面积", "各空间尺度、面积分配、比例关系"),
    ("detail", "局部深化", "某个局部的具体处理"),
)

LEVEL_ORDER = [lv[0] for lv in DESIGN_LEVELS]
LEVEL_LABELS = {lv[0]: lv[1] for lv in DESIGN_LEVELS}

# 建筑维度全景（P0-10 视野切换的认知地图）：
# 只作为"当前还能从哪些维度推进"的横向扫描提醒，不规定顺序、不要求全部扫描、
# 不自动推进。AI 判断"现在最值得推进什么"时参考它。
DESIGN_LANDSCAPE = (
    ("site", "场地与到达", "场地条件、周边关系、入口人流、朝向"),
    ("layout", "总体布局", "体块关系、与场地/周边的整体组织"),
    ("function", "功能关系", "功能分区、房间之间的靠近/隔开/共享"),
    ("organization", "空间组织", "核心空间、空间序列、动静分区"),
    ("circulation", "流线", "水平动线、垂直交通、疏散"),
    ("scale", "尺度", "建筑尺度、空间比例、人体尺度"),
    ("daylight", "采光", "朝向、开窗、自然光环境"),
    ("section", "剖面", "层高、剖面关系、空间竖向组织"),
    ("interior_exterior", "室内外关系", "庭院/平台/灰空间、与室外的连接"),
)


def record_design_progress(updated: dict, level: str) -> None:
    """记录本轮 AI 产出的设计粒度（去重保序，current 始终为最近一次产出）。"""
    if level not in LEVEL_ORDER:
        return
    progress = updated.setdefault("design_progress", {"levels": [], "current": ""})
    if level not in progress["levels"]:
        progress["levels"].append(level)
    progress["current"] = level


def _record_event(updated: dict, event: dict) -> None:
    """追加一条语义事件（写入 semantic_events，保留最近 200 条）。"""
    events = updated.setdefault("semantic_events", [])
    events.append(event)
    updated["semantic_events"] = events[-200:]


def register_pending_choice(updated: dict, choice_set: dict | None, turn_id: int) -> None:
    """AI 提出可选对象集（生成端 interaction 元数据）→ 注册为 pending_choice。

    choice_set: {"id": "library_role_01", "question": "...",
                 "options": [{"id": "a", "label": "社区客厅"}, ...]}
    旧的未消费 pending_choice 标记 consumed（一次只存在一个可指代对象集）。
    """
    if not choice_set or not choice_set.get("id") or not choice_set.get("options"):
        return
    prev = updated.get("pending_choice") or {}
    if prev.get("id") and prev.get("id") != choice_set["id"] and prev.get("status") == "open":
        prev["status"] = "consumed"
    updated["pending_choice"] = {
        "id": str(choice_set["id"])[:80],
        "question": str(choice_set.get("question", ""))[:300],
        "options": [
            {"id": str(o.get("id", ""))[:40], "label": str(o.get("label", ""))[:120]}
            for o in choice_set["options"] if o.get("id") or o.get("label")
        ],
        "turn_id": turn_id,
        "status": "open",
    }


# ── 语义事件解析（学生输入 → 事件）────────────────────────────────

# 序数/数字 → option 匹配（中文、英文、阿拉伯数字）
_ORDINAL_PATTERNS = (
    ("1", r"^1\b|^1[\.、）)]|第一个|第一种|选项一|方案一|方向一|option\s*1|option\s*a\b|^a\b|^a[\.、）)]"),
    ("2", r"^2\b|^2[\.、）)]|第二个|第二种|选项二|方案二|方向二|option\s*2|option\s*b\b|^b\b|^b[\.、）)]"),
    ("3", r"^3\b|^3[\.、）)]|第三个|第三种|选项三|方案三|方向三|option\s*3|option\s*c\b|^c\b|^c[\.、）)]"),
    ("4", r"^4\b|^4[\.、）)]|第四个|第四种|选项四|方案四|方向四|option\s*4|option\s*d\b|^d\b|^d[\.、）)]"),
    ("5", r"^5\b|^5[\.、）)]|第五个|第五种|选项五|方案五|方向五|option\s*5|option\s*e\b|^e\b|^e[\.、）)]"),
)

# 改选/否定信号（revise：旧选择作废，换新）
_REVISE_RE = re.compile(r"还是.{0,6}(?:第|那个|选项|方案|方向|[abcde一二三四五])|改(?:成|选|为)|换(?:成|一个|一下|个)|不要.{0,4}(?:这个|那个)|不算.{0,4}(?:这个|那个)|算了.{0,4}(?:选|要)|重新选")
# 弱否定/修正信号（correct：纠正一个事实候选/图纸事实）
_CORRECT_RE = re.compile(r"不是|没有|错了|不对|搞错|其实是|应该是|根本不是|哪是")
# 换主线信号（refocus：切换当前研究主题）
_REFOCUS_RE = re.compile(r"先不聊|别(?:聊|说|提)|换个(?:角度|话题|方向)|不聊.{0,6}(?:了)|我要看|我想看|回到(?:整体|布局|空间)|换一个话题")
# 授权信号（delegation）：用户把更多推演劳动临时交给 AI——不是决定、不是"继续问我"，
# 而是"你先往下做，我拿结果来批"。AI 应换一种工作方式（按合理假设推一版），不得复读原骨架或继续让学生选。
_DELEGATION_RE = re.compile(
    r"都可以[，,、]?(?:吧|啊)?你|你先(?:想|帮我想|来|做|看|给)|你来吧|你来|先给我一版|"
    r"随便.{0,4}你|你(?:来)?做一个|你先做一个|你看着办|听你的|你决定(?:吧)?|按你的(?:想法|来)|"
    r"你带我|你带着我|你帮我往下|交给你|你来推|你先推"
)
# 明确选择动词（"我选X""就选X""用X"）——把消息里的标签文本与选项匹配
_SELECT_VERB_RE = re.compile(r"我选|我就选|就选|用.{0,4}(?:这个|那个)|选.{0,6}(?:吧|了)|就要|就用|确定(?:选|用|要)|保留(?:这个|那个)|(?:选|用)(?:第)?")


def _match_option(text: str, options: list[dict]) -> dict | None:
    """把学生输入解析为 pending_choice 中的某个 option。

    支持：数字（2）、序数（第二个/option B）、英文选项（b）、
    标签文本匹配（"知识仓库那个""我选你说的知识仓库"）。
    """
    if not options:
        return None
    t = (text or "").strip().lower()
    # 1) 数字/序数/字母
    for index, pattern in _ORDINAL_PATTERNS:
        if re.search(pattern, t, re.I):
            # 精确到选项列表长度内
            idx = int(index) - 1
            if idx < len(options):
                return options[idx]
    # 2) 按标签文本匹配：直接命中或"那个/X 那个/说的 X"
    for opt in options:
        label = str(opt.get("label", "")).strip().lower()
        if not label:
            continue
        if label in t or t in label:
            return opt
        # "知识仓库那个" / "你说的知识仓库" / "就知识仓库吧"
        if re.search(rf"{re.escape(label)}", t):
            return opt
    return None


def apply_semantic_events(updated: dict, message: str, turn_id: int) -> list[dict]:
    """学生输入 → 语义事件 → 状态更新（确定性）。

    当前实现四类：select / revise / correct / refocus。
    返回本次产生的语义事件列表（供 chat_turn 记录 + 注入 context）。
    """
    applied: list[dict] = []
    text = (message or "").strip()

    # ── correct：纠正事实候选/图纸事实 ──
    # P0-A 硬不变量：不存在可指向的 active 视觉事实时，不产生 correct 事件
    # （"覆盖视觉识别"的前提是存在视觉事实；无视觉事实时任何"纠正"都无对象可覆盖）
    if _CORRECT_RE.search(text) and not _REVISE_RE.search(text) and _active_vision_facts(updated):
        fact_statement = detect_drawing_correction(text)
        if fact_statement:
            # 图纸事实纠正（已有真值层机制，升级为事件化）
            record_drawing_fact(updated, fact_statement, turn_id)
            event = {
                "type": "correct", "target_id": f"fact-{turn_id}",
                "payload": {"statement": fact_statement},
                "source": "student", "confidence": "high", "status": "applied",
                "turn_id": turn_id, "raw": text,
            }
            _record_event(updated, event)
            applied.append(event)
            return applied

    # ── refocus：换主线 ──
    if _REFOCUS_RE.search(text):
        # 提取新主题（"我要看空间布局" → "空间布局"；"回到整体布局" → "整体布局"）
        # 注意：优先匹配"我要看/回到"等明确指向词；"聊"只用于触发，不用于提取（避免抓到旧话题尾巴）
        m = re.search(r"(?:我要看|我想看|回到|看一下|看看|关注)(.{1,20}?)(?:吧|了|。|$)", text)
        new_topic = m.group(1).strip() if m else ""
        event = {
            "type": "refocus", "target_id": updated.get("design_focus", {}).get("topic", ""),
            "payload": {"new_topic": new_topic},
            "source": "student", "confidence": "medium", "status": "applied",
            "turn_id": turn_id, "raw": text,
        }
        _record_event(updated, event)
        applied.append(event)
        return applied

    # ── delegation：用户把推演劳动临时交给 AI（"都可以你先帮我想想""你先来"）──
    # 不是设计决定（不进 selected_options/student_decisions），也不是"继续问我"信号；
    # AI 应换工作方式：按合理假设往下推一版可批改的方案，不复读原骨架。
    if _DELEGATION_RE.search(text) and not _CORRECT_RE.search(text):
        event = {
            "type": "delegation", "target_id": updated.get("design_focus", {}).get("topic", ""),
            "payload": {"request": "把更多推演劳动临时交给 AI"},
            "source": "student", "confidence": "medium", "status": "applied",
            "turn_id": turn_id, "raw": text,
        }
        _record_event(updated, event)
        applied.append(event)
        return applied

    # ── select / revise：作用对象 = pending_choice ──
    pending = updated.get("pending_choice") or {}
    # select 只作用 open 的 choice_set；revise 允许作用最近一个 choice_set（即使已 consumed）
    is_revise = bool(_REVISE_RE.search(text))
    # 已有 active 选择时，任何新选择都视为改选（revise）
    has_active_selection = any(s.get("status") == "active" for s in updated.get("selected_options", []))
    if has_active_selection and _match_option(text, (pending or {}).get("options", [])):
        is_revise = True
    pending_valid = pending.get("status") in ("open", "consumed") if pending else False
    if pending and pending_valid:
        matched = _match_option(text, pending.get("options", []))
        # 纯选择/改选（数字、序数、标签命中）
        is_select_signal = bool(
            re.search(r"^\s*[1-5a-e]\s*$", text, re.I)
            or re.search(r"第[一二三四五12345]个", text)
            or re.search(r"我选|就选|选.{0,6}(?:吧|了)|就用|就要|确定选|保留这个", text)
            or is_revise
        )
        if is_select_signal and matched:
            # 旧选择作废
            for sel in updated.setdefault("selected_options", []):
                if sel.get("status") == "active":
                    sel["status"] = "revoked"
            updated["selected_options"].append({
                "choice_set_id": pending["id"],
                "option_id": matched["id"],
                "label": matched["label"],
                "source": "student",
                "status": "active",
                "turn_id": turn_id,
            })
            pending["status"] = "consumed"
            event = {
                "type": "revise" if is_revise else "select",
                "target_id": pending["id"],
                "payload": {"option_id": matched["id"], "label": matched["label"]},
                "source": "student", "confidence": "high", "status": "applied",
                "turn_id": turn_id, "raw": text,
            }
            _record_event(updated, event)
            applied.append(event)
        elif is_revise and not matched:
            # 改选但未识别新选项：仅记录改选意图（低置信），交 LLM
            event = {
                "type": "revise", "target_id": pending["id"],
                "payload": {"option_id": None, "label": ""},
                "source": "student", "confidence": "low", "status": "applied",
                "turn_id": turn_id, "raw": text,
            }
            _record_event(updated, event)
            applied.append(event)

    return applied


def semantic_context(updated: dict) -> dict:
    """把当前语义事件状态整理成给 LLM 的上下文（LLM 只读，不猜）。"""
    active_choices = [s for s in updated.get("selected_options", []) if s.get("status") == "active"]
    pending = updated.get("pending_choice") or {}
    return {
        "active_choices": active_choices,
        "pending_choice": pending if pending.get("status") == "open" else {},
    }
