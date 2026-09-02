"""语义事件层测试（V1.2）：select / revise / correct / refocus + pending_choice 注册 + interaction 解析。

原则：状态层存"语义事件"，不存"用户原句"；事件作用于结构化对象（choice_set_id）。
修复前这些场景全部失败（"2"被当普通文本、AI 靠猜）；修复后应全部通过。
"""

import unittest

from conversation_state import (apply_semantic_events, empty_state, register_pending_choice)
from architect_chat import _split_interaction


def _choice_set(choice_id="library_role_01"):
    return {
        "id": choice_id, "question": "哪种定位更贴合？",
        "options": [
            {"id": "a", "label": "社区客厅"},
            {"id": "b", "label": "知识仓库"},
            {"id": "c", "label": "活动中心"},
        ],
    }


class SemanticEventProtocolTests(unittest.TestCase):
    def _selections(self, state):
        return [(x["label"], x["status"]) for x in state.get("selected_options", [])]

    def test_pending_choice_registration(self):
        s = empty_state()
        register_pending_choice(s, _choice_set(), 1)
        self.assertEqual("library_role_01", s["pending_choice"]["id"])
        self.assertEqual("open", s["pending_choice"]["status"])
        self.assertEqual(3, len(s["pending_choice"]["options"]))

    def test_select_by_number_creates_semantic_event(self):
        s = empty_state()
        register_pending_choice(s, _choice_set(), 1)
        events = apply_semantic_events(s, "2", 2)
        self.assertEqual(["select"], [e["type"] for e in events])
        self.assertEqual([("知识仓库", "active")], self._selections(s))
        self.assertEqual("知识仓库", s["semantic_events"][-1]["payload"]["label"])
        self.assertEqual("library_role_01", s["semantic_events"][-1]["target_id"])

    def test_select_by_ordinal_zh(self):
        s = empty_state()
        register_pending_choice(s, _choice_set(), 1)
        apply_semantic_events(s, "第二个", 2)
        self.assertEqual([("知识仓库", "active")], self._selections(s))

    def test_select_by_label_text(self):
        s = empty_state()
        register_pending_choice(s, _choice_set(), 1)
        apply_semantic_events(s, "我选你说的知识仓库", 2)
        self.assertEqual([("知识仓库", "active")], self._selections(s))

    def test_select_by_english_option(self):
        s = empty_state()
        register_pending_choice(s, _choice_set(), 1)
        apply_semantic_events(s, "b", 2)
        self.assertEqual([("知识仓库", "active")], self._selections(s))

    def test_revise_revokes_old_and_activates_new(self):
        s = empty_state()
        register_pending_choice(s, _choice_set(), 1)
        apply_semantic_events(s, "2", 2)          # 知识仓库 active
        events = apply_semantic_events(s, "还是第三个吧", 3)  # 改选活动中心
        self.assertEqual(["revise"], [e["type"] for e in events])
        self.assertEqual(
            [("知识仓库", "revoked"), ("活动中心", "active")],
            self._selections(s),
        )

    def test_revise_with_option_letter_after_selection(self):
        s = empty_state()
        register_pending_choice(s, _choice_set(), 1)
        apply_semantic_events(s, "2", 2)
        apply_semantic_events(s, "option b", 4)
        self.assertEqual(
            [("知识仓库", "revoked"), ("知识仓库", "active")],
            self._selections(s),
        )

    def test_correct_records_drawing_fact_and_event(self):
        from conversation_state import register_vision_facts
        s = empty_state()
        register_vision_facts(s, [{"statement": "车库西侧有楼梯", "element": "楼梯", "location": "车库西侧"}], 1)
        events = apply_semantic_events(s, "车库西侧不是楼梯", 2)
        self.assertEqual(["correct"], [e["type"] for e in events])
        facts = s.get("drawing_facts", [])
        self.assertEqual(1, len(facts))
        self.assertEqual("confirmed", facts[0]["confidence"])

    def test_refocus_records_topic_switch(self):
        s = empty_state()
        events = apply_semantic_events(s, "先不聊这个，我要看空间布局", 3)
        self.assertEqual(["refocus"], [e["type"] for e in events])
        self.assertEqual("空间布局", events[0]["payload"]["new_topic"])

    def test_events_are_append_only(self):
        s = empty_state()
        register_pending_choice(s, _choice_set(), 1)
        apply_semantic_events(s, "2", 2)
        apply_semantic_events(s, "还是第三个吧", 3)
        types = [e["type"] for e in s["semantic_events"]]
        self.assertEqual(["select", "revise"], types)
        self.assertEqual(2, len(s["semantic_events"]))

    def test_delegation_signal_is_not_a_decision_or_question(self):
        """"都可以你先帮我想想"是把推演劳动交给 AI——不是决定、不是继续问我。"""
        s = empty_state()
        events = apply_semantic_events(s, "都可以吧，你先帮我想想", 2)
        self.assertEqual(["delegation"], [e["type"] for e in events])
        self.assertEqual([], s.get("selected_options", []), "授权不是设计决定")
        self.assertNotEqual([], s.get("semantic_events", []), "授权应被记录为语义事件")

    def test_delegation_variants(self):
        for msg in ("你先来", "先给我一版", "随便，你先做一个看看", "你带着我往下做吧", "你看着办"):
            s = empty_state()
            events = apply_semantic_events(s, msg, 1)
            self.assertEqual(["delegation"], [e["type"] for e in events], msg)


class MultiGoalSemanticStructureTests(unittest.TestCase):
    """多目标检测的语义结构识别：并列目标 vs 单一问题+条件/原因。"""

    def test_parallel_goals_trigger(self):
        from architect_chat import _detect_multi_goal
        goals = _detect_multi_goal("我想调整房间布局达到良好采光交通流线合理，房间布置合理")
        self.assertGreaterEqual(len(goals), 2)

    def test_single_problem_with_condition_does_not_trigger(self):
        """'客厅去卧室要穿庭院，流线有问题吗？'——庭院是条件不是并列目标。"""
        from architect_chat import _detect_multi_goal
        goals = _detect_multi_goal("流线有没有问题？客厅去卧室要穿庭院怎么办？")
        self.assertEqual([], goals)

    def test_single_problem_with_reason_does_not_trigger(self):
        """'采光不好是不是因为教学楼挡住了？'——教学楼遮挡是原因不是目标。"""
        from architect_chat import _detect_multi_goal
        goals = _detect_multi_goal("南向采光不好是不是因为前面的教学楼挡住了？")
        self.assertEqual([], goals)

    def test_single_judgment_does_not_trigger(self):
        from architect_chat import _detect_multi_goal
        self.assertEqual([], _detect_multi_goal("客厅朝北，采光会不会有问题"))
        self.assertEqual([], _detect_multi_goal("这个布局合理吗？"))

    def test_parallel_with_connector_triggers(self):
        from architect_chat import _detect_multi_goal
        goals = _detect_multi_goal("我想同时优化采光、流线和房间布局")
        self.assertGreaterEqual(len(goals), 2)

    def test_negated_or_corrective_goal_mentions_do_not_trigger(self):
        from architect_chat import _detect_multi_goal
        messages = (
            "我没有说采光和私密，也没有让你做价值排序。",
            "不要先问房间朝向，也别马上固定整体布局。",
            "不是要讨论采光、流线或庭院，我是在撤回上一套组织。",
            "你上一轮把采光和私密说成我的目标，但那不是我的意思。",
        )
        for message in messages:
            with self.subTest(message=message):
                self.assertEqual([], _detect_multi_goal(message))

    def test_goal_words_without_active_goal_intent_do_not_trigger(self):
        from architect_chat import _detect_multi_goal
        self.assertEqual([], _detect_multi_goal("先回到整体，后面再谈采光、流线和布局。"))

    def test_affirmative_parallel_goal_variants_still_trigger(self):
        from architect_chat import _detect_multi_goal
        messages = (
            "我希望兼顾采光和私密。",
            "采光、流线和庭院关系对我都重要。",
            "既要改善流线，也要保证庭院完整。",
        )
        for message in messages:
            with self.subTest(message=message):
                self.assertGreaterEqual(len(_detect_multi_goal(message)), 2)


class DesignProgressTests(unittest.TestCase):
    """设计产出记忆：已做过什么被记录；delegation 时注入全景地图而非强制流水线。"""

    def test_record_progress_keeps_memory(self):
        from conversation_state import record_design_progress
        s = empty_state()
        record_design_progress(s, "function_relations")
        record_design_progress(s, "space_organization")
        self.assertEqual(["function_relations", "space_organization"], s["design_progress"]["levels"])
        self.assertEqual("space_organization", s["design_progress"]["current"])

    def test_duplicate_level_does_not_duplicate(self):
        from conversation_state import record_design_progress
        s = empty_state()
        record_design_progress(s, "function_relations")
        record_design_progress(s, "space_organization")
        record_design_progress(s, "function_relations")
        self.assertEqual(["function_relations", "space_organization"], s["design_progress"]["levels"])

    def test_delegation_guide_injects_landscape_not_pipeline(self):
        """delegation 引导注入建筑维度全景 + 论证义务，而非"必须推进到 X"。"""
        from conversation_state import empty_state, record_design_progress
        from architect_chat import _build_delegation_guide
        s = empty_state()
        record_design_progress(s, "function_relations")
        record_design_progress(s, "space_organization")
        guide = _build_delegation_guide(s)
        # 记忆：已产出内容被列出
        self.assertIn("功能关系", guide)
        self.assertIn("空间组织骨架", guide)
        # 全景：可扫描的维度被列出（含场地、剖面——不按功能→空间的固定序）
        self.assertIn("场地与到达", guide)
        self.assertIn("剖面", guide)
        self.assertIn("采光", guide)
        # 论证义务：要求说明选择理由
        self.assertIn("说明你选择该维度的理由", guide)
        # 不强制"必须推进到落位"（无固定下一级）
        self.assertNotIn("必须推进到", guide)

    def test_landscape_allows_jumping_back(self):
        """全景地图允许跳回任何维度（包括已产出之外、或更早的维度）。"""
        from conversation_state import DESIGN_LANDSCAPE
        labels = [lv[1] for lv in DESIGN_LANDSCAPE]
        self.assertIn("场地与到达", labels)
        self.assertIn("剖面", labels)
        self.assertIn("室内外关系", labels)


class DrawingCorrectionSemanticTests(unittest.TestCase):
    """图纸纠正的语义结构：否定/替换/更正，而非图面词命中。"""

    def _detect(self, msg):
        from conversation_state import detect_drawing_correction
        return detect_drawing_correction(msg)

    def test_real_corrections_trigger(self):
        for msg in (
            "车库西侧那个不是楼梯",
            "你看错了，这里是窗，不是门",
            "刚才说的 14000 不对，是 14500",
            "这个房间其实是书房",
            "应该是一层不是二层",
        ):
            self.assertIsNotNone(self._detect(msg), msg)

    def test_questions_do_not_trigger(self):
        for msg in (
            "流线有没有问题？客厅去卧室要穿庭院怎么办？",
            "这里为什么要穿庭院？",
            "这个窗采光怎么样？",
            "楼梯放这里合理吗？",
            "客厅去卧室要穿庭院合理吗？",
        ):
            self.assertIsNone(self._detect(msg), msg)

    def test_correction_through_semantic_event(self):
        """correct 语义事件只在有可指向视觉事实时触发。"""
        from conversation_state import register_vision_facts
        s = empty_state()
        register_vision_facts(s, [{"statement": "车库西侧有楼梯", "element": "楼梯", "location": "车库西侧"}], 1)
        events = apply_semantic_events(s, "车库西侧不是楼梯", 2)
        self.assertEqual(["correct"], [e["type"] for e in events])
        self.assertEqual(1, len(s.get("drawing_facts", [])))

    def test_question_does_not_create_correct_event(self):
        """'流线有没有问题？' 是提问，不是 correct 事件。"""
        s = empty_state()
        events = apply_semantic_events(s, "流线有没有问题？客厅去卧室要穿庭院怎么办？", 2)
        self.assertNotIn("correct", [e["type"] for e in events])
        self.assertEqual([], s.get("drawing_facts", []))


class MetaFeedbackIsolationTests(unittest.TestCase):
    """A：元对话与设计状态隔离（支持混合意图）。

    四条验收：
    1. 纯元反馈 → 不改任何设计状态
    2. 元反馈+设计问题 → 回应 bug，同时正常回答设计问题
    3. 元反馈+设计否定 → "为什么一直讲"不污染状态，"不想做中庭"正常进 reject
    4. 元反馈+refocus → focus 切到整体布局，不因元反馈整句忽略
    """

    def _split(self, msg):
        from conversation_state import split_meta_feedback
        return split_meta_feedback(msg)

    def test_pure_meta_feedback_isolated(self):
        meta, design = self._split("你刚才是不是出bug了？")
        self.assertEqual(["你刚才是不是出bug了？"], meta)
        self.assertEqual("", design)

    def test_meta_plus_design_question(self):
        meta, design = self._split("你刚才那三句重复了。另外错层会不会太碎？")
        self.assertTrue(any("重复" in m for m in meta), f"meta={meta}")
        self.assertIn("错层会不会太碎", design)

    def test_meta_plus_design_reject(self):
        meta, design = self._split("你为什么一直讲中庭？我已经不想做中庭了。")
        self.assertTrue(any("一直讲中庭" in m for m in meta), f"meta={meta}")
        self.assertIn("不想做中庭", design)

    def test_meta_plus_refocus_same_sentence(self):
        meta, design = self._split("你刚才理解错了，先别聊儿童区，我想先看整体布局。")
        self.assertTrue(any("理解错" in m for m in meta))
        self.assertIn("先别聊儿童区", design)
        self.assertIn("整体布局", design)

    def test_pure_design_not_meta(self):
        for msg in ("错层会不会把空间搞碎？", "你觉得儿童阅览放哪合适？", "我不想做中庭了，先看入口吧。", "我收回刚才关于中庭的决定"):
            meta, design = self._split(msg)
            self.assertEqual([], meta, msg)
            self.assertIn("儿童阅览" if "儿童" in msg else msg[:4], design)

    def test_chat_turn_meta_feedback_does_not_corrupt_state(self):
        """验收1：纯元反馈轮次不得改变任何设计状态。"""
        from architect_chat import chat_turn
        from unittest.mock import patch
        s = empty_state()
        s["design_focus"]["topic"] = "儿童阅览"
        with patch("architect_chat._call_deepseek", return_value="抱歉，那是系统输出卡住导致的，跟你的方案无关。我们继续。"):
            r = chat_turn("你刚才是不是出bug了？", [], s, turn_id=2)
        st = r["state"]
        self.assertEqual("儿童阅览", st["design_focus"]["topic"], "元反馈不得改 design_focus")
        self.assertEqual([], st["student_decisions"], "元反馈不得产生设计决定")
        self.assertEqual("", st.get("pending_clarification", ""), "元反馈不得触发澄清卡死")

    def test_chat_turn_meta_plus_reject_state_updated(self):
        """验收3：元反馈不污染状态，但'不想做中庭'必须进入 reject/revise。"""
        from architect_chat import chat_turn
        from unittest.mock import patch
        s = empty_state()
        s["student_decisions"] = [{"value": "中庭作为核心", "turn_id": 1, "source": "student"}]
        with patch("architect_chat._call_deepseek", return_value="好，收回中庭作为核心的决定，我们重新看。你想从哪开始？"):
            r = chat_turn("你为什么一直讲中庭？我已经不想做中庭了。", [], s, turn_id=2)
        st = r["state"]
        self.assertEqual([], st["student_decisions"], "'不想做中庭'应撤销中庭决定")
        self.assertNotIn("中庭作为核心", [d.get("value") for d in st["student_decisions"]])


class StateRevisionRefocusTests(unittest.TestCase):
    """A3：试验性意图不得被状态修正器升级为 refocus。"""

    def test_trial_intent_does_not_switch_design_focus(self):
        from architect_chat import _apply_state_revision
        from conversation_state import set_design_focus

        s = empty_state()
        set_design_focus(s, "公共性按到达方式组织", 1)
        opener = _apply_state_revision(
            s,
            "南边大台阶只是个想法，你先别把整个建筑都按到达方式组织，我只是想试试二层能不能也开放。",
            2,
        )

        self.assertEqual("", opener)
        self.assertEqual("公共性按到达方式组织", s["design_focus"]["topic"])
        self.assertFalse(any(h.get("status") == "dormant" for h in s["design_focus"]["history"]))

    def test_explicit_refocus_still_switches_design_focus(self):
        from architect_chat import _apply_state_revision
        from conversation_state import set_design_focus

        s = empty_state()
        set_design_focus(s, "共享庭院组织", 1)
        opener = _apply_state_revision(s, "我们换个方向，我就想设计分散体块。", 2)

        self.assertIn("分散体块", s["design_focus"]["topic"])
        self.assertTrue(any(h.get("status") == "dormant" for h in s["design_focus"]["history"]))
        self.assertIn("收回", opener)


class VisionOverrideInvariantTests(unittest.TestCase):
    """视觉覆盖不变量：不存在的证据不能被覆盖。

    1. 无图片 + 设计陈述 → 绝不 visual override
    2. 无图片 + 学生提供图纸事实 → 记录 student fact，非 vision override
    3. 有视觉事实 + 明确纠正 → 覆盖对应 visual fact（具体 id）
    4. 多视觉事实 + 模糊纠正 → 不得一锅端全部作废
    """

    def _record(self, state, msg, turn=2):
        from conversation_state import record_drawing_fact
        record_drawing_fact(state, msg, turn)

    def test_no_vision_no_override_for_design_statement(self):
        s = empty_state()
        self._record(s, "我倾向两层", 1)
        f = s["drawing_facts"][0]
        self.assertEqual("student", f["source"])
        self.assertNotIn("overrides", f, "无视觉事实不得产生 overrides")

    def test_no_vision_student_fact_not_correction(self):
        s = empty_state()
        self._record(s, "这里其实是储藏间")
        f = s["drawing_facts"][0]
        self.assertEqual("student", f["source"])
        self.assertNotIn("overrides", f)

    def test_with_vision_correction_overrides_specific_id(self):
        from conversation_state import register_vision_facts
        s = empty_state()
        register_vision_facts(s, [{"statement": "车库西侧有楼梯", "element": "楼梯", "location": "车库西侧"}], 1)
        self._record(s, "车库西侧不是楼梯，是储藏间", 2)
        f = s["drawing_facts"][0]
        self.assertEqual("student_correction", f["source"])
        self.assertEqual("vision-1-0", f["overrides"], "应指向具体视觉事实 id")

    def test_vague_correction_does_not_override_all(self):
        from conversation_state import register_vision_facts
        s = empty_state()
        register_vision_facts(s, [
            {"statement": "车库西侧有楼梯"},
            {"statement": "客厅在北侧"},
        ], 1)
        self._record(s, "你看错了，整体都画得不对", 2)
        f = s["drawing_facts"][0]
        self.assertNotIn("overrides", f, "模糊纠正不得锅端视觉事实")
        statuses = [c["status"] for c in s["fact_candidates"]]
        self.assertEqual(["candidate", "candidate"], statuses, "视觉事实不得被一锅端作废")

    def test_unrelated_correction_targets_only_matching(self):
        from conversation_state import register_vision_facts
        s = empty_state()
        register_vision_facts(s, [
            {"statement": "车库西侧有楼梯"},
            {"statement": "客厅在北侧"},
        ], 1)
        self._record(s, "那个不是楼梯", 2)
        f = s["drawing_facts"][0]
        self.assertEqual("vision-1-0", f["overrides"], "只覆盖同主题的楼梯事实")


class P0A_NoVisionNoOverrideTests(unittest.TestCase):
    """P0-A 硬不变量：不存在可指向的 active 视觉事实时，绝不产生 visual override。"""

    def test_pure_text_first_round_no_vision_override(self):
        """纯文本首轮（无图）不触发'视觉识别作废'，不残留假 drawing_fact。"""
        from architect_chat import chat_turn
        from unittest.mock import patch
        msg = ("老师让我做一个3000平左右的社区文化中心，场地大概40×55米，东边是社区主路，南边有一个小公园，"
               "北边是几栋住宅，西边是社区内部步行路。功能有展览、舞蹈教室、绘画教室、多功能厅、社区会议室、"
               "咖啡、办公后勤。我比较想让这个建筑平时不是上课才有人，而是居民路过也愿意进来坐一坐。")
        with patch("architect_chat._call_deepseek", return_value="好，我们从头看这个社区文化中心。"):
            r = chat_turn(msg, [], empty_state(), turn_id=1)
        self.assertNotIn("视觉识别", r["reply"], "无视觉事实不得说'视觉识别作废'")
        self.assertNotIn("已记下", r["reply"])
        self.assertEqual([], r["state"].get("drawing_facts", []), "不得残留假图纸事实")
        self.assertFalse(any(e.get("type") == "correct" for e in r["state"].get("semantic_events", [])))

    def test_no_vision_correct_event_not_produced(self):
        """无视觉事实时，即使消息含'不是'也不产生 correct 事件。"""
        s = empty_state()
        ev = apply_semantic_events(s, "车库西侧不是楼梯", 1)
        self.assertFalse(any(e["type"] == "correct" for e in ev))
        self.assertEqual([], s.get("drawing_facts", []))

    def test_with_vision_correction_still_works(self):
        """有视觉事实时纠正仍生效且指向具体 id（不变量不误伤真实纠正）。"""
        from conversation_state import register_vision_facts
        s = empty_state()
        register_vision_facts(s, [{"statement": "车库西侧有楼梯", "element": "楼梯", "location": "车库西侧"}], 1)
        ev = apply_semantic_events(s, "车库西侧不是楼梯，是储藏间", 2)
        self.assertTrue(any(e["type"] == "correct" for e in ev))
        f = s["drawing_facts"][0]
        self.assertEqual("vision-1-0", f["overrides"])

    def test_with_image_context_correction_works_in_chat_turn(self):
        """有图上下文时 chat_turn 的纠正路径照常走通（不变量不破坏有图路径）。"""
        from architect_chat import chat_turn
        from unittest.mock import patch
        fc = [{"id": "f1", "filename": "55.jpg", "kind": "image", "source": "vision", "status": "reference_only",
               "visible_facts": ["车库西侧有楼梯"]}]
        with patch("architect_chat._call_deepseek", return_value="好，按你的确认为准，车库西侧是储藏间。"):
            r = chat_turn("车库西侧不是楼梯，是储藏间", [], empty_state(), turn_id=2, file_contexts=fc)
        self.assertGreaterEqual(len(r["state"].get("drawing_facts", [])), 1, "有图时纠正应被记录")


class InteractionParsingTests(unittest.TestCase):
    def test_split_interaction_removes_marker(self):
        reply = (
            "1. 社区客厅\n2. 知识仓库\n\n你先想想。\n"
            '<interaction>{"type":"choice_set","id":"library_role_01","question":"q",'
            '"options":[{"id":"a","label":"社区客厅"},{"id":"b","label":"知识仓库"}]}</interaction>'
        )
        clean, interaction = _split_interaction(reply)
        self.assertNotIn("<interaction>", clean)
        self.assertEqual("choice_set", interaction["type"])
        self.assertEqual("library_role_01", interaction["id"])
        self.assertEqual("知识仓库", interaction["options"][1]["label"])

    def test_split_interaction_no_marker(self):
        clean, interaction = _split_interaction("普通回复，没有选项。")
        self.assertEqual("普通回复，没有选项。", clean)
        self.assertIsNone(interaction)

    def test_split_interaction_bad_json_falls_back_to_clean(self):
        reply = "回复<interaction>not json</interaction>尾巴"
        clean, interaction = _split_interaction(reply)
        self.assertIsNone(interaction)
        self.assertIn("回复", clean)
        self.assertIn("尾巴", clean)


if __name__ == "__main__":
    unittest.main()
