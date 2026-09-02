import unittest
from unittest.mock import patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import architect_chat as ac


class CandidateCommitmentBoundaryTests(unittest.TestCase):
    def test_no_choice_request_is_not_recorded_as_student_decision(self):
        message = (
            "可是你这个不还是让大家围着中间一个院子吗？"
            "我刚才说了不想靠一个中心。你别再换个名字绕回来，"
            "按我说的‘各自独立但别太散’重新想一个，直接给我关系，"
            "不用再让我选类型。"
        )
        state = {
            "issue_register": {},
            "student_decisions": [],
            "change_log": [],
        }

        ac._apply_issue_confirmation(state, message, 6)

        self.assertEqual("rejected", ac._candidate_commitment_status(message))
        self.assertEqual([], state["student_decisions"])

    def test_candidate_commitment_status_distinguishes_transition_intent(self):
        cases = {
            "我觉得这个方向感觉不错，可以继续看看。": "candidate",
            "先不要定死，继续深化看看。": "candidate",
            "还没确定采用，就继续看看。": "candidate",
            "那就按这个做。": "confirmed",
            "行，就这么做吧，中庭就定下来。": "confirmed",
            "这个方案定了，继续深化。": "confirmed",
            "采用这个方向，继续做。": "confirmed",
            "这个方向不要了，换一个方向。": "rejected",
            "不是这个方向，换一个。": "rejected",
            "我不想用大厅当心脏，换一种没那么中心化的。": "rejected",
            "线性这个有点像走廊，我不是很喜欢，换个思路吧。": "rejected",
            "这种组织关系我不太接受，请换一种关系。": "rejected",
            "我不想继续沿用刚才的逻辑，给我别的组织关系。": "rejected",
            "请解释一下什么是建筑流线。": "none",
            "这个方案不是很复杂，可以继续分析。": "none",
        }

        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(expected, ac._candidate_commitment_status(message))

    def test_rejection_has_priority_over_candidate_language(self):
        message = "中庭方向听起来不错，但我现在不要了，请换一个方向继续看看。"

        self.assertEqual("rejected", ac._candidate_commitment_status(message))
        self.assertFalse(ac._is_candidate_commitment_turn(message))

    def test_candidate_boolean_uses_status_protocol(self):
        self.assertTrue(ac._is_candidate_commitment_turn("先不要定死，继续深化看看。"))
        self.assertFalse(ac._is_candidate_commitment_turn("那就按这个做。"))
        self.assertFalse(ac._is_candidate_commitment_turn("这个方向不要了。"))

    def test_natural_confirmation_is_recorded_as_student_decision(self):
        state = {"issue_register": {}, "student_decisions": [], "change_log": []}

        ac._apply_issue_confirmation(
            state,
            "那就按这个做。中央中庭方案定了，请继续深化。",
            2,
        )

        self.assertEqual(1, len(state["student_decisions"]))
        self.assertEqual("student", state["student_decisions"][0]["source"])
        self.assertIn("中央中庭方案定了", state["student_decisions"][0]["value"])

    def test_colloquial_confirmation_activates_existing_candidate_without_refocus(self):
        state = {
            "issue_register": {
                "issue-1-1": {
                    "text": "中央中庭作为公共空间组织候选",
                    "origin": "ai",
                    "status": "candidate",
                }
            },
            "student_decisions": [],
            "change_log": [],
            "design_focus": {"topic": "", "history": []},
        }
        message = "行，就这么做吧，中庭就定下来，继续深化入口和剖面。"

        opener = ac._apply_state_revision(state, message, 2)
        ac._apply_issue_confirmation(state, message, 2)

        self.assertEqual("", opener)
        self.assertEqual("active", state["issue_register"]["issue-1-1"]["status"])
        self.assertEqual(1, len(state["student_decisions"]))

    def test_explicit_rejection_marks_existing_candidate_rejected(self):
        state = {
            "issue_register": {
                "issue-1-1": {
                    "text": "中央中庭作为公共空间组织候选",
                    "origin": "ai",
                    "status": "candidate",
                }
            },
            "student_decisions": [],
            "change_log": [],
            "design_focus": {"topic": "", "history": []},
            "rejected_assumptions": [],
        }

        ac._apply_state_revision(
            state,
            "这个不太行，我不想要中庭了，换个不依赖中庭的方向。",
            2,
        )

        self.assertEqual("rejected", state["issue_register"]["issue-1-1"]["status"])

    def test_weak_natural_rejection_updates_issue_state_before_generation(self):
        state = {
            "issue_register": {
                "issue-1-1": {
                    "text": "线性路径组织空间",
                    "origin": "ai",
                    "status": "candidate",
                }
            },
            "student_decisions": [],
            "change_log": [],
            "design_focus": {"topic": "线性路径组织空间", "history": []},
            "rejected_assumptions": [],
        }

        opener = ac._apply_state_revision(
            state,
            "线性这个有点像走廊，我不是很喜欢，换个思路吧。",
            5,
        )

        self.assertEqual("rejected", state["issue_register"]["issue-1-1"]["status"])
        self.assertTrue(state["rejected_assumptions"])
        self.assertIn("先放下", opener)

    def test_do_not_choose_for_me_is_not_recorded_as_confirmation(self):
        state = {"issue_register": {}, "student_decisions": [], "change_log": []}

        ac._apply_issue_confirmation(
            state,
            "我不想要双入口这个候选。继续推单入口，但不要替我选。",
            2,
        )

        self.assertEqual([], state["student_decisions"])

    def test_confirmation_context_persists_and_rejection_overrides_it(self):
        state = {
            "student_decisions": [
                {"value": "中央中庭方案定了", "turn_id": 2, "source": "student"}
            ]
        }
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            continued = ac._apply_candidate_confirmation_context(
                "base policy", "继续深化入口和剖面。", state, "design_request"
            )
            rejected = ac._apply_candidate_confirmation_context(
                "base policy", "这个方向不要了，换一个方向。", state, "design_request"
            )

            self.assertIn("中央中庭方案定了", continued)
            self.assertIn("不得降级为候选", continued)
            self.assertNotIn("中央中庭方案定了", rejected)
            self.assertIn("明确拒绝", rejected)
            self.assertIn("不得换名复活", rejected)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_confirmation_context_forbids_derived_details_inheriting_confirmation(self):
        state = {
            "student_decisions": [{
                "value": "我决定采用东侧单入口、连续公共带和局部通高",
                "turn_id": 12,
                "source": "student",
            }]
        }
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            policy = ac._apply_candidate_confirmation_context(
                "base policy",
                "请整理当前两层空间骨架，不要提问。",
                state,
                "design_request",
            )

            self.assertIn("我决定采用东侧单入口、连续公共带和局部通高", policy)
            self.assertIn("确认身份不得传递给推导结果", policy)
            self.assertIn("位置、方向、顺序、邻接、流线、体量或剖面", policy)
            self.assertIn("只能标为候选", policy)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_candidate_commitment_boundary_is_noop_when_disabled(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = False
            policy = ac._apply_candidate_commitment_boundary_policy(
                "base policy",
                "我觉得中央中庭可能不错，继续深化看看。",
                "design_request",
            )
            self.assertEqual(policy, "base policy")
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_candidate_commitment_boundary_injects_generator_guard_when_enabled(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            candidate_messages = (
                "我觉得中央中庭挺有意思，可以继续深化看看。",
                "北侧入口是不是更好？",
                "庭院方案听起来不错，先按这个试一版。",
                "我有点喜欢线性街道式空间，但还没想好。",
                "我还没确定采用中庭，继续看看。",
                "三个方案哪个最好，你直接帮我选。",
                "如果入口放东侧，会不会更有公共性？",
            )
            for message in candidate_messages:
                with self.subTest(message=message):
                    policy = ac._apply_candidate_commitment_boundary_policy(
                        "base policy", message, "design_request"
                    )
                    self.assertIn("Candidate Commitment Boundary", policy)
                    self.assertIn("允许展开候选", policy)
                    self.assertIn("禁止写成学生已经确定采用", policy)
                    self.assertIn("问题本身不得预设", policy)
                    self.assertIn("评价标准或缺失条件", policy)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_rejecting_old_route_keeps_new_route_from_becoming_default(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            policy = ac._apply_candidate_commitment_boundary_policy(
                "base policy",
                (
                    "我不想要双入口这个候选了。换成只设一个入口、同时和公园保持联系的方向继续推，"
                    "但入口在哪一侧还没有决定。"
                ),
                "design_request",
            )

            self.assertIn("Candidate Commitment Boundary", policy)
            self.assertIn("不得选择其中一个作为默认路线", policy)
            self.assertIn("并列候选", policy)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_candidate_body_removes_default_route_after_declaring_choice_suspended(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "入口在哪一侧、主要人流从哪来都还不知道，所以暂时悬置。"
                "可以先按‘入口在北侧、公园做侧景’推一版，等有人流证据再检验。"
            )
            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "我不想要双入口了，换成单入口继续推，但入口在哪一侧还没有决定。",
                "design_request",
                {},
            )

            self.assertNotIn("可以先按‘入口在北侧、公园做侧景’推一版", result)
            self.assertIn("并列作为候选", result)
            self.assertIn("不作为默认路线", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_candidate_body_removes_default_assumption_with_lai_tui_wording(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            drafts = (
                (
                    "两个入口方向都还没有决定。"
                    "如果你不确定，可以先按‘支路是主要到达’来推，后续再校验。"
                ),
                (
                    "两个入口方向都无法判定更优。"
                    "如果没有资料，我们可以先按‘北侧支路是主要到达界面’这个假设往下推一版骨架，"
                    "等信息出来再校验。"
                ),
            )
            for draft in drafts:
                with self.subTest(draft=draft):
                    result = ac._apply_candidate_commitment_body_boundary(
                        draft,
                        "入口放北侧还是东侧还没决定，不要默认任何一侧。",
                        "design_request",
                        {},
                    )

                    self.assertNotIn("先按", result)
                    self.assertIn("不作为默认路线", result)
                    self.assertNotIn("作为一版起点只作为", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_candidate_body_does_not_call_exploration_a_confirmed_direction(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            result = ac._apply_candidate_commitment_body_boundary(
                "单入口与公园联系——这是你确认的方向。下面给两个可画候选。",
                "继续推单入口和公园联系，但不要替我选。",
                "design_request",
                {},
            )

            self.assertNotIn("这是你确认的方向", result)
            self.assertIn("当前探索的候选方向", result)
            self.assertIn("两个可画候选", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_vague_design_goal_triggers_route_guidance_guard(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            messages = (
                "我想做一个更开放、更有社区感的文化中心。",
                "我希望空间自然一点，也更通透。",
                "想让这个纪念馆更有仪式感。",
            )
            for message in messages:
                with self.subTest(message=message):
                    policy = ac._apply_candidate_commitment_boundary_policy(
                        "base policy", message, "design_request"
                    )
                    self.assertIn("Candidate Commitment Boundary", policy)
                    self.assertIn("不得把抽象目标直接绑定", policy)
                    self.assertIn("路线来源", policy)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_ai_introduced_form_is_removed_from_final_question_only(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先给一版公共大厅串联展览和咖啡的可画骨架。\n\n"
                "这个公共大厅做通高还是两层挑空？"
            )
            result = ac._apply_candidate_route_question_boundary(
                draft,
                "我想做得更开放、更有社区感。",
                {},
                "general_advice",
            )

            self.assertIn("先给一版公共大厅串联展览和咖啡的可画骨架。", result)
            self.assertNotIn("这个公共大厅做通高还是两层挑空？", result)
            self.assertIn("保留、调整或放弃", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_user_introduced_form_can_remain_in_final_question(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = "先展开中央中庭候选。\n\n这个中庭更偏停留还是交通？"

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "我觉得中央中庭挺有意思，可以继续深化看看。",
                {},
                "design_request",
            )

            self.assertEqual(draft, result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_weak_ack_does_not_take_ownership_of_ai_candidate_route(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先继续展开中央中庭测试骨架。\n\n"
                "这个中庭更偏交通枢纽还是停留场所？"
            )
            state = {
                "issue_register": {
                    "issue-1-1": {
                        "text": "中央中庭作为公共空间组织候选",
                        "origin": "ai",
                        "status": "candidate",
                    }
                },
                "framework_trail": [{
                    "text": "中央中庭作为公共空间组织候选",
                    "origin": "ai_suggestion",
                    "status": "proposed",
                }],
            }

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "嗯，这个中庭听着还可以，你接着往下弄吧。",
                state,
                "design_request",
            )

            self.assertNotIn("交通枢纽还是停留场所", result)
            self.assertIn("检验上面的测试骨架", result)
            self.assertIn("保留、调整或放弃", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_weak_ack_ai_candidate_open_vs_separated_question_is_rewritten(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先继续展开中央中庭测试骨架。\n\n"
                "儿童活动和中庭之间完全开放还是设置分隔？"
            )
            state = {
                "issue_register": {
                    "issue-1-1": {
                        "text": "中央中庭作为公共空间组织候选",
                        "origin": "ai",
                        "status": "candidate",
                    }
                }
            }

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "这个中庭听着还行，再往下做具体点。",
                state,
                "design_request",
            )

            self.assertNotIn("完全开放还是设置分隔", result)
            self.assertIn("保留、调整或放弃", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_route_question_patch_preserves_draw_action_in_same_paragraph(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draw_action = "把门厅、中庭和大空间画成一条主轴，两侧挂上小房间。"
            draft = (
                "先给一版可画骨架。\n\n"
                + draw_action
                + "先看这个关系是否接受。画完告诉我：这个中庭做通高还是局部挑空？"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "我希望空间自然、通透。",
                {},
                "general_advice",
            )

            self.assertIn(draw_action, result)
            self.assertIn("先看这个关系是否接受。", result)
            self.assertNotIn("这个中庭做通高还是局部挑空？", result)
            self.assertIn("保留、调整或放弃", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_confirmed_form_can_remain_in_final_question(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = "先展开中央中庭。\n\n这个中庭更偏停留还是交通？"
            state = {"student_decisions": [{"value": "采用中央中庭"}]}

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "我希望空间更开放一些。",
                state,
                "design_request",
            )

            self.assertEqual(draft, result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_route_question_boundary_is_noop_when_disabled(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = False
            draft = "先给一版光庭骨架。\n\n这个光庭做方形还是圆形？"

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "我希望空间自然、通透。",
                {},
                "design_request",
            )

            self.assertEqual(draft, result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_route_source_benchmark_covers_common_ai_introduced_forms(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            forms = ("中庭", "庭院", "公共大厅", "社区客厅", "线性街道", "光庭", "回廊")
            for form in forms:
                with self.subTest(form=form):
                    draft = f"先给一版可画骨架。\n\n这个{form}做集中式还是分散式？"
                    result = ac._apply_candidate_route_question_boundary(
                        draft,
                        "我希望空间更开放、更自然。",
                        {},
                        "general_advice",
                    )
                    self.assertNotIn(f"这个{form}做集中式还是分散式？", result)
                    self.assertIn("保留、调整或放弃", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_form_in_body_does_not_trigger_when_final_question_asks_goal(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先给一版以中庭串联功能的可画骨架。\n\n"
                "你更重视日常交流、空间体验，还是使用效率？"
            )
            result = ac._apply_candidate_route_question_boundary(
                draft,
                "我希望空间更开放、更自然。",
                {},
                "general_advice",
            )
            self.assertEqual(draft, result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_ai_introduced_arrival_categories_are_not_forced_on_student(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先给一版入口和公共空间并列比较的可画骨架。\n\n"
                "入口主要服务车行和城市步行，还是公园漫步？"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "我希望居民平时路过也愿意进来坐一坐。",
                {},
                "design_request",
            )

            self.assertNotIn("车行和城市步行，还是公园漫步", result)
            self.assertIn("不要求你在这些分类中选择", result)
            self.assertIn("可画骨架", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_ai_introduced_site_relation_categories_are_not_forced_on_student(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先把建筑与公园的边界画成三种可替换关系。\n\n"
                "公园联系以视线、路径还是空间渗透为主？"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "我想让空间更开放、更自然。",
                {},
                "design_request",
            )

            self.assertNotIn("视线、路径还是空间渗透", result)
            self.assertIn("不要求你在这些分类中选择", result)
            self.assertIn("三种可替换关系", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_ai_introduced_program_role_categories_are_not_forced_on_student(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先画出公共带与教学空间的邻接骨架。\n\n"
                "小剧场和舞蹈教室是公共带节点，还是独立房间？"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "我希望公共活动之间有联系，可以继续推推看。",
                {},
                "design_request",
            )

            self.assertNotIn("公共带节点，还是独立房间", result)
            self.assertIn("不要求你在这些分类中选择", result)
            self.assertIn("邻接骨架", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_student_owned_route_categories_can_remain_in_question(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先比较你提出的两种公园联系方式。\n\n"
                "公园联系以视线还是路径为主？"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "我想比较视线联系和路径联系，可以继续看看。",
                {},
                "design_request",
            )

            self.assertEqual(draft, result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_ai_core_program_role_taxonomy_is_not_forced_on_student(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先梳理现有功能之间的关系。\n\n"
                "你心里最核心的空间角色是什么？是社区的客厅，还是学习的场所，"
                "还是展示与演出的舞台？"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "你像导师一样陪我往下做，但不要替我定方案。",
                {},
                "design_request",
            )

            self.assertNotIn("最核心的空间角色", result)
            self.assertNotIn("社区的客厅，还是学习的场所", result)
            self.assertIn("不要求你在这些分类中选择", result)
            self.assertIn("梳理现有功能", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_ai_shared_vs_separate_space_taxonomy_is_not_forced_on_student(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先把停留目标拆成可操作的空间关系。\n\n"
                "你心里的停留更接近哪一种？A. 一个共享的大空间；"
                "B. 几个相对独立的小空间；C. 其他图景？"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "不要先替我绑定中庭、主街或庭院。",
                {},
                "design_request",
            )

            self.assertNotIn("更接近哪一种", result)
            self.assertNotIn("共享的大空间", result)
            self.assertIn("不要求你在这些分类中选择", result)
            self.assertIn("可操作的空间关系", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_audit_of_premature_commitment_is_not_classified_as_confirmation(self):
        messages = (
            "请检查你的问题有没有偷偷要求我在这些分类中拍板。",
            "不要替我拍板。",
            "不要替我决定。",
            "我还没有拍板，只是想继续看看。",
        )
        for message in messages:
            with self.subTest(message=message):
                self.assertNotEqual("confirmed", ac._candidate_commitment_status(message))

    def test_explicitly_unsettled_route_and_no_proxy_choice_stay_candidate(self):
        messages = (
            "入口和空间组织都没定，请给两个骨架，不要替我选。",
            "到达方向仍未定，你可以比较，但别代替我选择。",
            "请给两个可以比较、修改，也可以放弃的整体方向。",
        )
        for message in messages:
            with self.subTest(message=message):
                self.assertEqual("candidate", ac._candidate_commitment_status(message))

    def test_actual_rejection_is_distinct_from_permission_to_abandon(self):
        self.assertEqual(
            "rejected",
            ac._candidate_commitment_status("我决定放弃方向 A，回到整体重新看。"),
        )
        self.assertEqual(
            "candidate",
            ac._candidate_commitment_status("方向 A 只是可以放弃的草案，我还没决定。"),
        )

    def test_negated_proxy_choice_does_not_confirm_ai_issue(self):
        state = {
            "student_decisions": [],
            "issue_register": {
                "ai-route": {
                    "text": "北侧入口作为当前到达路线",
                    "origin": "ai",
                    "status": "candidate",
                }
            },
            "change_log": [],
        }

        ac._apply_issue_confirmation(
            state,
            "入口仍然没定，先比较两个方案，不要替我选。",
            turn_id=3,
        )

        self.assertEqual([], state["student_decisions"])
        self.assertEqual("candidate", state["issue_register"]["ai-route"]["status"])

    def test_unconfirmed_entrance_cannot_become_default_drawing_route(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            message = "入口和整体组织仍未定，请给我候选，但不要替我选。"
            drafts = (
                "北侧和东侧都是入口候选。现在不用选，先按北侧主入口画，东侧留一个开口。",
                "两个方向先并列比较。默认以东侧入口继续推一版，再看是否合适。",
                "如果资料还不确定，可以先拿 A 作为起点，再继续画入口关系。",
                "两者都没确认，优先从北侧入口方向开始推进会更省事。",
            )
            for draft in drafts:
                with self.subTest(draft=draft):
                    result = ac._apply_candidate_commitment_body_boundary(
                        draft,
                        message,
                        "design_request",
                        {"student_decisions": []},
                    )
                    self.assertNotIn("先按北侧主入口画", result)
                    self.assertNotIn("默认以东侧入口继续推", result)
                    self.assertNotIn("先拿 A 作为起点", result)
                    self.assertNotIn("优先从北侧入口方向开始", result)
                    self.assertIn("候选", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_ai_introduced_experience_binary_is_not_forced_on_student(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先画北侧道路到东侧绿地的测试路径。\n\n"
                "如果人从北侧进来，这条路径是越走越安静还是越走越活跃？"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "入口和室外联系还没有定，请推进，但不要用问题偷偷预设路线。",
                {},
                "design_request",
            )

            self.assertNotIn("越走越安静还是越走越活跃", result)
            self.assertIn("不要求你在这些分类中选择", result)
            self.assertIn("测试路径", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_explicit_no_preset_request_blocks_any_ai_choice_question(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            drafts = (
                (
                    "先从人的停留行为开始画。\n\n"
                    "你想象他正在做什么？是坐着看书，还是站着张望，还是找地方歇脚？"
                ),
                (
                    "先画道路和绿地的场地关系。\n\n"
                    "他是先看见绿地再进建筑，还是先进建筑再发现绿地？"
                ),
                (
                    "先把两条条件线放在同一张图上。\n\n"
                    "你觉得交汇位置是冲突还是可以共存？"
                ),
            )
            messages = (
                "不要先给我一组空间类别让我选。",
                "请推进，但不要用问题偷偷预设路线。",
                "继续给一个不依赖选边的可画动作。",
            )
            forbidden = ("坐着看书，还是", "先看见绿地再进建筑", "冲突还是可以共存")

            for draft, message, phrase in zip(drafts, messages, forbidden):
                with self.subTest(message=message):
                    result = ac._apply_candidate_route_question_boundary(
                        draft,
                        message,
                        {},
                        "design_request",
                    )
                    self.assertNotIn(phrase, result)
                    self.assertIn("不要求你在这些分类中选择", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_unresolved_entrance_wording_is_candidate_state(self):
        messages = (
            "入口和室外联系还没有定。",
            "入口还没定，请先推进关系。",
        )
        for message in messages:
            with self.subTest(message=message):
                self.assertEqual("candidate", ac._candidate_commitment_status(message))

    def test_explicit_no_preset_request_removes_body_choice_commitment(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "入口暂定在北侧，对着道路。\n"
                "绿地可以作为背景，也可以作为延伸。你可以选一种，也可以都不选。\n"
                "确定绿地是‘背景’还是‘延伸’后，我们再讨论开窗还是开门。"
            )

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "入口和室外联系还没有定，请推进，但不要用问题偷偷预设路线。",
                "design_request",
                {},
            )

            self.assertNotIn("入口暂定在北侧", result)
            self.assertNotIn("你可以选一种", result)
            self.assertNotIn("确定绿地是‘背景’还是‘延伸’后", result)
            self.assertIn("不作为暂定方向", result)
            self.assertIn("不要求在其中选择", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_ai_introduced_route_pronoun_choice_is_rewritten(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            drafts = (
                (
                    "先给一版以公共大厅组织功能的可画骨架。\n\n"
                    "这个方向更偏集中还是分散？"
                ),
                (
                    "先给一版线性公共主街串联功能的可画骨架。\n\n"
                    "这条公共主街更偏穿行还是停留？"
                ),
            )
            for draft in drafts:
                with self.subTest(draft=draft):
                    result = ac._apply_candidate_route_question_boundary(
                        draft,
                        "我希望空间更开放、更有社区感。",
                        {},
                        "design_request",
                    )
                    self.assertNotEqual(draft, result)
                    self.assertIn("保留、调整或放弃", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_ai_route_can_end_with_open_evaluation_question(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先给一版以公共大厅组织功能的可画骨架。\n\n"
                "这个测试骨架是否回应了你说的开放和社区感？"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "我希望空间更开放、更有社区感。",
                {},
                "design_request",
            )

            self.assertEqual(draft, result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_user_introduced_public_street_can_be_deepened(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = "先展开公共主街候选。\n\n这条公共主街更偏穿行还是停留？"

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "我想试试公共主街这个方向，继续深化看看。",
                {},
                "design_request",
            )

            self.assertEqual(draft, result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_user_route_can_compare_an_unsourced_component_option(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先展开公共主街候选。\n\n"
                "这条公共主街靠外墙获得自然光，还是夹在功能之间并通过天窗或中庭采光？"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "我想试试公共主街这个方向，继续深化看看。",
                {},
                "design_request",
            )

            self.assertEqual(draft, result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_explicit_body_commitment_is_downgraded_on_candidate_turn(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "你的方案采用中央中庭作为核心组织。"
                "主入口应该放在北侧。"
                "下面继续给出功能关系和可画动作。"
            )

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "我觉得中央中庭挺有意思，可以继续深化看看。",
                "design_request",
            )

            self.assertNotIn("你的方案采用", result)
            self.assertNotIn("主入口应该", result)
            self.assertIn("候选", result)
            self.assertIn("功能关系和可画动作", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_legal_candidate_deepening_is_preserved_in_body(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "这是你目前的一个设计倾向，还不是最终决定。"
                "可以先按核心组织空间试一版，再检验它是否成立。"
            )

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "我觉得中央中庭挺有意思，可以继续深化看看。",
                "design_request",
            )

            self.assertEqual(draft, result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_candidate_body_boundary_covers_explicit_commitment_phrases(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            cases = (
                ("我们确定采用线性街道组织。", "候选方向"),
                ("主入口应该设置在东侧。", "主入口候选"),
                ("这个方向确定成立，继续画平面。", "候选继续验证"),
            )
            for draft, expected in cases:
                with self.subTest(draft=draft):
                    result = ac._apply_candidate_commitment_body_boundary(
                        draft,
                        "这个方向听起来不错，继续推推看。",
                        "design_request",
                    )
                    self.assertIn(expected, result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_candidate_body_boundary_preserves_confirmed_user_decision(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = "你的方案采用中央中庭作为核心组织。"

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "我决定采用中央中庭方案，请继续深化。",
                "design_request",
            )

            self.assertEqual(draft, result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_candidate_body_boundary_is_noop_when_disabled(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = False
            draft = "主入口应该放在北侧。"

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "北侧入口是不是更好？",
                "design_request",
            )

            self.assertEqual(draft, result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_unconfirmed_history_is_not_written_as_previously_accepted(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "你之前接受的一层关系是‘门厅+咖啡→阅览→儿童’。"
                "现在继续把半开放小院接到这条渐变带上。"
            )

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "先把半开放小院当成候选试一下，我还没有决定。",
                "general_architecture_chat",
                {},
            )

            self.assertNotIn("你之前接受", result)
            self.assertIn("尚未确认", result)
            self.assertIn("半开放小院", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_real_confirmed_history_is_preserved(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = "你之前确认的内部小院可以继续深化剖面关系。"
            state = {
                "student_decisions": [{
                    "value": "我决定采用内部小院方案",
                    "status": "confirmed",
                    "source": "student",
                }]
            }

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "剖面可以先继续推推看。",
                "general_architecture_chat",
                state,
            )

            self.assertEqual(draft, result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_ai_core_interface_binary_is_opened_back_up(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先分析东侧道路和南侧滨水界面的影响。\n\n"
                "你希望建筑被看见的核心界面是哪一个——东侧社区道路，还是南侧滨水绿带？"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "我想让人从外面看到阅读，而且南边水边挺吸引人，是不是主要阅览可以放南侧？",
                {},
                "project_brief",
            )

            self.assertNotIn("核心界面是哪一个", result)
            self.assertIn("保留、调整或放弃", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_ai_extreme_value_binary_is_opened_back_up(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先比较儿童区与成人阅览的关系。\n\n"
                "你希望儿童区是建筑里最活跃开放的独立单元，还是藏在深处的封闭区域？"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "儿童区要不要靠西侧并和室外活动场地联系？帮我比较一下关系。",
                {},
                "general_architecture_chat",
            )

            self.assertNotIn("最活跃开放", result)
            self.assertNotIn("藏在深处", result)
            self.assertIn("保留、调整或放弃", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_historical_unconditional_entrance_commitments_are_downgraded(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            historical_replies = (
                (
                    "你提到北侧临城市道路、南侧是住宅，这个判断方向是对的。"
                    "北侧作为主要人流来向，入口放在北侧确实更符合从城市进入建筑的自然逻辑。"
                ),
                "你的直觉是对的，北侧作为主入口确实更合理。",
                "北侧作为主入口，方向是对的。",
            )
            for draft in historical_replies:
                with self.subTest(draft=draft):
                    result = ac._apply_candidate_commitment_body_boundary(
                        draft,
                        "基地北侧临城市道路，南侧住宅。入口放北侧是不是更好？",
                        "design_request",
                    )
                    self.assertNotIn("方向是对的", result)
                    self.assertNotIn("确实更合理", result)
                    self.assertNotIn("确实更符合", result)
                    self.assertIn("候选", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_conditional_entrance_comparison_is_preserved(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "如果主要人流从北侧城市道路到达，那么北侧入口在到达意义上是顺的；"
                "目前缺少这个数据，不能据此说北侧更好。"
            )

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "北侧入口是不是更好？",
                "design_request",
            )

            self.assertEqual(draft, result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_candidate_commitment_boundary_skips_confirmed_but_guards_replacement_after_rejection(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            confirmed_messages = (
                "我决定采用中央中庭方案，请继续深化。",
                "确定采用北侧入口，就按这个继续。",
                "就用这个方案。",
            )
            for message in confirmed_messages:
                with self.subTest(message=message):
                    policy = ac._apply_candidate_commitment_boundary_policy(
                        "base policy", message, "design_request"
                    )
                    self.assertEqual("base policy", policy)

            rejected = ac._apply_candidate_commitment_boundary_policy(
                "base policy",
                "之前考虑中庭，现在不想要了，换一个方向。",
                "design_request",
            )
            self.assertIn("Candidate Commitment Boundary", rejected)
            self.assertIn("不得选择其中一个作为默认路线", rejected)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_candidate_commitment_boundary_skips_non_design_request(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            policy = ac._apply_candidate_commitment_boundary_policy(
                "base policy",
                "我觉得中央中庭可能不错，继续深化看看。",
                "general_architecture_chat",
            )
            self.assertEqual("base policy", policy)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_weak_ack_of_ai_option_does_not_commit_in_reply_body(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            state = {
                "ai_contributions": [{
                    "value": (
                        "A. 路过时看到内部活动，被吸引进来。\n"
                        "B. 本来就想找地方停留。"
                    ),
                    "source": "ai",
                    "status": "reference_only",
                }]
            }
            draft = (
                "好，那就先按 A 走——‘被看见’这个方向。"
                "你要的不是建筑开放，而是内部活动能被路过的人看见。"
                "下面继续给出界面、剖面和可画动作。"
            )

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "A听着好像可以，就先按这个看看吧，具体怎么做我也不懂。",
                "general_architecture_chat",
                state,
            )

            self.assertNotIn("先按 A 走", result)
            self.assertNotIn("你要的不是", result)
            self.assertIn("待检验候选", result)
            self.assertIn("界面、剖面和可画动作", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_weak_ack_of_ai_option_uses_question_to_test_candidate(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            state = {
                "ai_contributions": [{
                    "value": (
                        "A. 路过时看到内部活动，被吸引进来。\n"
                        "B. 本来就想找地方停留。"
                    ),
                    "source": "ai",
                    "status": "reference_only",
                }]
            }
            draft = (
                "先把‘被看见’展开成临街界面、入口展示和局部挑空三个可画动作。\n\n"
                "你希望‘被看见’是从外面看里面，还是也包括建筑内部上下层互相看见？"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "A听着好像可以，就先按这个看看吧，具体怎么做我也不懂。",
                state,
                "general_architecture_chat",
            )

            self.assertNotIn("从外面看里面，还是", result)
            self.assertIn("检验", result)
            self.assertIn("保留、调整或放弃", result)
            self.assertIn("临街界面、入口展示和局部挑空", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_weak_ack_does_not_become_selected_scheme_wording(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            state = {
                "ai_contributions": [{
                    "value": "方向 A：沿公共走道开窗。\n方向 B：把工坊推到公共空间边缘。",
                    "source": "ai",
                    "status": "reference_only",
                }]
            }
            draft = (
                "好，那就先按方案 A 试，但这不是决定。"
                "你选 A 作为起点，意味着你暂时接受了北侧界面开放。"
                "下面继续给出局部关系和可画动作。"
            )

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "A 看起来比较容易，我先照着试试看，但现在还不想定下来。",
                "general_architecture_chat",
                state,
            )

            self.assertNotIn("先按方案 A", result)
            self.assertNotIn("你选 A 作为起点", result)
            self.assertNotIn("你暂时接受了", result)
            self.assertIn("待检验候选", result)
            self.assertIn("局部关系和可画动作", result)
            self.assertNotIn("。，", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_rejected_route_does_not_end_with_replacement_binary(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "A 已经放下。这里给 C 和 D 两个新角度作为并列候选。\n\n"
                "你更希望它是公园边打开的屋子，还是连接公园和马路的廊子？"
            )
            message = "我不想继续 A 了，C 和 D 我也没决定，能不能换个角度看？"

            self.assertEqual("rejected", ac._candidate_commitment_status(message))
            result = ac._apply_candidate_route_question_boundary(
                draft,
                message,
                {},
                "general_architecture_chat",
            )

            self.assertNotIn("还是连接公园", result)
            self.assertIn("保留、调整或放弃", result)
            self.assertIn("C 和 D 两个新角度", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_question_patch_preserves_content_after_the_question(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先换到空间体验角度。\n\n"
                "你更希望它安静还是热闹？\n"
                "可以继续观察光线、停留方式和活动关系。\n"
                "这三个观察点都可以转成草图。"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "我不想继续 A 了，请换个角度，但不要马上再让我二选一。",
                {},
                "general_architecture_chat",
            )

            self.assertNotIn("安静还是热闹", result)
            self.assertIn("光线、停留方式和活动关系", result)
            self.assertIn("这三个观察点都可以转成草图", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_weak_ack_does_not_become_current_acceptance_wording(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "好，入口的三层关系你认可了，那我们把门斗的玻璃和走道接上。"
                "下面继续给出局部关系和可画动作。"
            )
            message = "这个局部好像可以，再把玻璃界面和走道说清楚一点。"

            self.assertEqual("candidate", ac._candidate_commitment_status(message))

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                message,
                "general_architecture_chat",
                {"student_decisions": []},
            )

            self.assertNotIn("你认可了", result)
            self.assertIn("继续检验", result)
            self.assertIn("局部关系和可画动作", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_explicitly_confirmed_relation_keeps_acceptance_wording(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = "你已经确认采用中央中庭，我们继续深化入口和流线。"
            state = {
                "student_decisions": [{
                    "value": "我决定采用中央中庭。",
                    "source": "student",
                }]
            }

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "继续深化入口和流线。",
                "design_request",
                state,
            )

            self.assertEqual(draft, result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_candidate_identity_persists_when_next_turn_only_requests_detail(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            state = {
                "student_decisions": [],
                "issue_register": {
                    "issue-a": {
                        "text": "方向 A：入口和灰空间形成连续过渡带",
                        "origin": "ai",
                        "status": "candidate",
                    }
                },
            }
            draft = (
                "既然你选了 A，我们把入口和灰空间组织成连续过渡带。"
                "你选的这个局部会影响后面的走道。"
            )

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "把 A 里面入口和灰空间的局部关系说具体一点。",
                "general_architecture_chat",
                state,
            )

            self.assertNotIn("既然你选了", result)
            self.assertNotIn("你选的这个局部", result)
            self.assertIn("继续检验", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_suspended_default_route_rewrite_does_not_leave_broken_prefix(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = "好，那我们就先按 A 入口方向试一版，但它不是你的决定。"

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "A 听起来容易一点，我先试试看，但没有决定采用。",
                "general_architecture_chat",
                {},
            )

            self.assertNotIn("那我们就“A”", result)
            self.assertIn("不作为默认路线", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_unconfirmed_ownership_attribution_is_source_checked_not_phrase_specific(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = "这些是你在讨论中接受的空间关系，我们继续深化体量。"

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "可以继续看看，但我没有确认这些关系。",
                "general_architecture_chat",
                {"student_decisions": []},
            )

            self.assertNotIn("你在讨论中接受的", result)
            self.assertIn("当前继续检验", result)
            self.assertIn("继续深化体量", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_rejection_downgrades_new_route_authority_by_semantic_class(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "这种功能分组是比场地关系更合理的整体逻辑。"
                "公共核心自然临街，教学带自然向花园延伸。"
                "这栋楼其实有两条流线。"
                "下面仍然给出功能关系、主流线和可画动作。"
            )

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "之前的方向不要了，请从整体重新看。",
                "design_request",
                {},
            )

            self.assertNotIn("更合理的整体逻辑", result)
            self.assertNotIn("自然临街", result)
            self.assertNotIn("自然向花园", result)
            self.assertNotIn("其实有两条流线", result)
            self.assertIn("待检验", result)
            self.assertIn("功能关系、主流线和可画动作", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_numbered_question_section_is_replaced_atomically(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "先给出一个完整的功能关系和主流线候选。\n\n"
                "画完看三件事：\n"
                "1. 你更想选中央中庭还是线性街道？\n"
                "2. 教学区向花园延伸，这个方向你认不认？\n"
                "3. 如果花园人少，是否改回临街组织？如果花园"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "旧方向不要了，请重新看整体，但不要替我选择。",
                {},
                "design_request",
            )

            self.assertIn("完整的功能关系和主流线候选", result)
            self.assertIn("保留、调整或放弃", result)
            self.assertNotIn("中央中庭还是线性街道", result)
            self.assertNotIn("如果花园", result)
            self.assertFalse(result.rstrip().endswith("如果"))
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_no_default_request_blocks_ai_defined_comparison_dimensions(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            drafts = (
                (
                    "前面保留了两套完整空间骨架。\n\n"
                    "你更想先比较哪个维度——入口与公园的关系，还是公共空间的性格（外向还是内向）？"
                ),
                (
                    "两套方案都保留功能关系和可画动作。\n\n"
                    "接下来先看沿街开放还是内向庭院？"
                ),
            )
            message = "两种都先保留，别帮我选定，也不要暗中默认某一种先做。"

            for draft in drafts:
                with self.subTest(draft=draft):
                    result = ac._apply_candidate_route_question_boundary(
                        draft,
                        message,
                        {},
                        "compare_cases",
                    )

                    self.assertNotEqual(draft, result)
                    self.assertNotIn("入口与公园的关系，还是", result)
                    self.assertNotIn("沿街开放还是内向庭院", result)
                    self.assertIn("回应你的目标和场地条件", result)
                    self.assertIn("可以保留、调整或放弃", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_rejection_with_proxy_decision_language_is_not_confirmation(self):
        message = (
            "这个公共客厅我不太想要，感觉被它绑住了。"
            "请退回来看看整体，但别偷偷替我决定。"
        )

        self.assertEqual("rejected", ac._candidate_commitment_status(message))

    def test_proxy_decision_language_cannot_activate_ai_issue(self):
        state = {
            "issue_register": {
                "issue-a": {
                    "text": "公共客厅作为整体组织核心",
                    "origin": "ai",
                    "status": "candidate",
                }
            },
            "student_decisions": [],
        }
        message = "这个公共客厅我不太想要，请退回来，但别偷偷替我决定。"

        ac._apply_issue_confirmation(state, message, 3)

        self.assertEqual("candidate", state["issue_register"]["issue-a"]["status"])
        self.assertEqual([], state["student_decisions"])

    def test_real_first_person_decision_remains_confirmation(self):
        self.assertEqual(
            "confirmed",
            ac._candidate_commitment_status("我决定采用中央中庭，请继续深化。"),
        )

    def test_no_default_request_removes_choice_invitation_without_question_mark(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            drafts = (
                "两套方向都可以调整。作为起点，先分清你更想强调哪一边。",
                "三种姿势只是候选。你先感受一下哪个方向更对味，或者都不要。",
                "两个骨架都能改。下一步你可以先选一个方向，再往下推。",
                "两版先并列。或者告诉我你更在意进门的感觉还是功能怎么摆。",
            )
            message = "先都保留，别替我选，也不要暗中默认一个方向。"

            for draft in drafts:
                with self.subTest(draft=draft):
                    result = ac._apply_candidate_commitment_body_boundary(
                        draft,
                        message,
                        "design_request",
                        {},
                    )

                    self.assertNotIn("更想强调哪一边", result)
                    self.assertNotIn("哪个方向更对味", result)
                    self.assertNotIn("先选一个方向", result)
                    self.assertNotIn("更在意进门的感觉还是功能怎么摆", result)
                    self.assertIn("并列检验", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_parallel_comparison_drops_unauthorized_third_default_deepening(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "**想法 A：向外打开**\n保留完整功能关系和体量方向。\n\n"
                "**想法 B：内向院落**\n保留另一套空间骨架和可画动作。\n\n"
                "我先按“北入口 + 东向打开 + 西侧辅助”这个混合骨架往下推了一版空间组织。\n"
                "入口层采用北侧门厅，公共层沿东侧展开，后面继续详细深化。"
            )

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "两套都先保留，不要悄悄拿一个当默认。",
                "compare_cases",
                {},
            )

            self.assertIn("想法 A", result)
            self.assertIn("想法 B", result)
            self.assertIn("完整功能关系和体量方向", result)
            self.assertNotIn("我先按", result)
            self.assertNotIn("入口层采用北侧门厅", result)
            self.assertIn("不作为默认路线", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_colloquial_do_not_choose_blocks_ai_choice_question(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "两套空间骨架已经按同等粒度展开。\n\n"
                "这两个骨架哪个方向更吸引你，还是先聊建筑的感觉？"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "先给我比较，但别替我选，也别拿一个继续往下做。",
                {},
                "compare_cases",
            )

            self.assertNotIn("哪个方向更吸引你", result)
            self.assertIn("可以保留、调整或放弃", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_no_choice_request_removes_numbered_choice_tail_across_paragraphs(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "两套功能关系、空间骨架和可画动作都已给出。\n\n"
                "现在你可以做两件事之一：\n"
                "1. 选沿边展开还是中心凝聚。\n"
                "2. 先聊建筑感觉。\n\n"
                "你想先往哪个方向走？"
            )

            result = ac._apply_candidate_route_question_boundary(
                draft,
                "入口和组织都没定，别替我选。",
                {},
                "compare_cases",
            )

            self.assertIn("功能关系、空间骨架和可画动作", result)
            self.assertNotIn("现在你可以做两件事之一", result)
            self.assertNotIn("哪个方向走", result)
            self.assertIn("可以保留、调整或放弃", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_no_choice_request_removes_declarative_type_selection(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "三个组团以多个局部联系保持可达。\n\n"
                "如果这个方向对，下一步我们要定的是：这些联系具体怎么做——"
                "是短廊、是窗洞、还是半开放平台，这会决定空间体验。"
            )
            message = "直接给我关系，不用再让我选类型。"

            result = ac._apply_candidate_commitment_body_boundary(
                draft, message, "design_request", {}
            )

            self.assertIn("多个局部联系", result)
            self.assertNotIn("下一步我们要定的是", result)
            self.assertNotIn("还是半开放平台", result)
            self.assertIn("检验", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_removed_choice_question_drops_markdown_choice_rationale(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "已经给出多个局部联系和可画动作。\n\n"
                "**你更想把联系做成短廊还是半室外平台？** "
                "这个选择会决定独立和联系的平衡点。"
            )
            message = "直接给我关系，不用再让我选类型。"

            result = ac._apply_candidate_route_question_boundary(
                draft, message, {}, "design_request"
            )

            self.assertNotIn("短廊还是半室外平台", result)
            self.assertNotIn("这个选择会决定", result)
            self.assertNotIn("** 这个选择", result)
            self.assertIn("不要求你在这些分类中选择", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_unconfirmed_entrance_stays_candidate_across_comparison(self):
        old_enabled = ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY
        try:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = True
            draft = (
                "**骨架 A：北入口 + 沿边公共带**\n"
                "入口放在北侧小路，进入后沿公共带展开。\n"
                "**骨架 B：中心公共核**\n"
                "北侧仍然做入口，北入口 → 中心核 → 各功能。\n"
                "北侧临社区路放主入口和门厅。\n"
                "主入口开在东侧社区路。"
            )

            result = ac._apply_candidate_commitment_body_boundary(
                draft,
                "入口和组织方式都没定，请比较但别替我选。",
                "compare_cases",
                {},
            )

            self.assertNotIn("入口放在北侧小路", result)
            self.assertNotIn("北侧仍然做入口", result)
            self.assertNotIn("北侧临社区路放主入口", result)
            self.assertNotIn("主入口开在东侧社区路", result)
            self.assertIn("入口候选", result)
        finally:
            ac.ENABLE_CANDIDATE_COMMITMENT_BOUNDARY = old_enabled

    def test_rejected_central_topology_cannot_return_as_shared_courtyard(self):
        draft = (
            "三个独立功能块围着半开放共享庭院布置。"
            "三个区的门都开向庭院，人站在院子里能看到所有入口。"
        )
        message = "我不想靠一个中心组织，也不要再换成院子绕回来。"
        rewritten = (
            "三个功能块保持独立，以两两邻接形成多个局部联系。"
            "各连接点分别承担到达，不依赖共同中心。"
        )

        with patch.object(ac, "_boundary_rewrite", return_value=rewritten) as rewrite:
            result = ac._apply_rejected_route_topology_boundary(draft, message)

        self.assertEqual(rewritten, result)
        rewrite.assert_called_once()
        self.assertNotIn("都开向庭院", result)

    def test_rejected_central_topology_cannot_return_as_shared_void(self):
        draft = (
            "进来之后直接面对一个开放的室外空隙，不是围合的院子，是几块之间的留白。"
            "四个盒子之间只留空隙，人站在空隙里，一眼能看到四个盒子的入口。"
        )
        message = "我不想靠一个中心，你别再换个名字绕回来。"
        rewritten = (
            "功能分成两组邻接单元，每组分别设置到达点。"
            "两组之间通过两个局部联系互相看见，不依赖共同留白。"
        )

        with patch.object(ac, "_boundary_rewrite", return_value=rewritten) as rewrite:
            result = ac._apply_rejected_route_topology_boundary(draft, message)

        self.assertEqual(rewritten, result)
        rewrite.assert_called_once()
        self.assertNotIn("站在空隙里", result)

    def test_rejected_central_topology_cannot_return_as_shared_node(self):
        draft = (
            "四个小房子彼此形成几组相邻关系，再靠一个共享的交通节点把它们连起来。"
            "这个节点只是十字路口，承担分流和转向。"
            "站在节点里能同时看到几个体块的入口。"
        )
        message = "我不想靠一个中心，别再换个名字绕回来。"
        rewritten = (
            "四个功能块形成两组邻接单元，分别设置到达点。"
            "组间通过两个局部联系互相可达，不依赖共同节点。"
        )

        with patch.object(ac, "_boundary_rewrite", return_value=rewritten) as rewrite:
            result = ac._apply_rejected_route_topology_boundary(draft, message)

        self.assertEqual(rewritten, result)
        rewrite.assert_called_once()
        self.assertNotIn("共享的交通节点", result)

    def test_rejected_central_topology_cannot_keep_unique_junction(self):
        draft = (
            "A 和 C 之间不直接连通，靠北侧入口的小前厅作为唯一的交汇点。"
            "这个小前厅只够分流，不承担中心角色。"
        )
        message = "我不想靠一个中心，直接给我多个局部关系。"
        rewritten = "A 与 B、B 与 C 分别建立局部联系，不设置唯一交汇点。"

        with patch.object(ac, "_boundary_rewrite", return_value=rewritten) as rewrite:
            result = ac._apply_rejected_route_topology_boundary(draft, message)

        self.assertEqual(rewritten, result)
        rewrite.assert_called_once()
        self.assertNotIn("作为唯一的交汇点", result)

    def test_explicit_rename_complaint_forces_semantic_topology_rewrite(self):
        draft = (
            "三个组团围出一个空的交叉空间，只是一个三岔口。"
            "站在交叉口能同时看到另外两个组团的入口。"
        )
        message = "我不想靠一个中心，你别再换个名字绕回来。"
        rewritten = (
            "剧场与活动室、活动室与阅览分别建立局部联系，"
            "设置两个独立到达点，不共享交汇空间。"
        )

        with patch.object(ac, "_boundary_rewrite", return_value=rewritten) as rewrite:
            result = ac._apply_rejected_route_topology_boundary(draft, message)

        self.assertEqual(rewritten, result)
        rewrite.assert_called_once()

    def test_abstract_unchanged_relation_feedback_forces_rewrite(self):
        draft = "所有功能都依赖同一个媒介完成到达、识别和分流。"
        message = (
            "你只是换了表达，组织关系根本没有变。"
            "不要继续沿用同一个全局组织者。"
        )
        rewritten = (
            "设置两个独立联系点，分别服务不同的相邻功能；"
            "各联系发生在不同位置。"
        )

        with patch.object(ac, "_boundary_rewrite", return_value=rewritten) as rewrite:
            result = ac._apply_rejected_route_topology_boundary(draft, message)

        self.assertEqual(rewritten, result)
        rewrite.assert_called_once()

    def test_abstract_single_global_organizer_is_topology_conflict(self):
        draft = "全部功能通过同一个组织媒介完成连接和分流。"
        message = "不要让任何单一要素统一组织所有空间。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("centralized_organizer", conflicts)

    def test_abstract_single_connector_between_groups_is_topology_conflict(self):
        draft = "两个组团之间只通过一个联系媒介保持关联。"
        message = "不要再依赖一条主线组织空间，各部分应有多个局部联系。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("single_linear_organizer", conflicts)

    def test_cross_sentence_shared_organizer_is_topology_conflict(self):
        draft = (
            "四个功能各自成块。它们共同面向一个共享对象。"
            "这个对象承担全部单元的识别、到达与联系。"
        )
        message = "我不想依赖一个中心，请改用多个局部联系。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("centralized_organizer", conflicts)

    def test_cross_sentence_single_global_mediator_is_topology_conflict(self):
        draft = (
            "三个组团分别独立，彼此之间只保留一个中介对象。"
            "它的唯一作用是让全部组团相互感知。"
        )
        message = "不要再依赖一条主线组织空间，各部分应有多个局部联系。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("single_linear_organizer", conflicts)

    def test_single_shared_referent_linking_all_participants_is_topology_conflict(self):
        draft = "若干单元各自独立，中间用一个共同对象把它们连起来。"
        message = "我不想依赖一个中心，请改用多个局部联系。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("centralized_organizer", conflicts)

    def test_singular_between_relation_with_unique_role_is_topology_conflict(self):
        draft = (
            "这三块之间留出一条介入关系。"
            "这条关系的作用只有一个：让三块之间互相看得见。"
        )
        message = "不要再依赖一条主线组织空间，各部分应有多个局部联系。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("single_linear_organizer", conflicts)

    def test_shared_referent_with_anaphoric_global_role_is_topology_conflict(self):
        draft = (
            "设置一个共同对象，只承担停留。"
            "它让三个独立单元互相看得见，并维持这些单元的整体联系。"
        )
        message = "我不想依赖一个中心，请改用多个局部联系。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("centralized_organizer", conflicts)

    def test_all_participants_surrounding_one_referent_is_topology_conflict(self):
        draft = "若干单元各自独立，但整体仍围绕一个共同对象布置。"
        message = "我不想依赖一个中心，请改用多个局部联系。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("centralized_organizer", conflicts)

    def test_bare_surround_relation_to_one_shared_referent_is_conflict(self):
        draft = "三个独立单元围一个共同对象。"
        message = "我不想依赖一个中心，请改用多个局部联系。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("centralized_organizer", conflicts)

    def test_enclosing_relation_creating_one_shared_referent_is_conflict(self):
        draft = "四个部分共同围合出一个联系对象。"
        message = "不要再用单一全局媒介组织全部空间。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("centralized_organizer", conflicts)

    def test_global_participants_depending_on_one_abstract_mediator_is_conflict(self):
        draft = "所有部分的到达与识别都依赖一个共同媒介。"
        message = "不要再依赖一条主线组织空间。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("single_linear_organizer", conflicts)

    def test_one_mediator_carrying_overall_relation_is_global_conflict(self):
        draft = "一条介入关系承担整体联系。"
        message = "不要再依赖一条主线组织空间。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("single_linear_organizer", conflicts)

    def test_one_referent_organizing_multiple_participants_in_reverse_order_is_conflict(self):
        draft = "从入口先到中间一个对象，再在四周挂三个独立组。"
        message = "我不想依赖一个中心，请改用多个局部联系。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("centralized_organizer", conflicts)

    def test_pairwise_local_relations_do_not_form_global_single_dependency(self):
        draft = (
            "甲与乙形成一处局部联系，乙与丙另设一处联系。"
            "每组之间各画一条短线，发生在不同位置。"
        )
        message = "我不想依赖一个中心，也不要一条主线。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertEqual(set(), conflicts)

    def test_one_referent_between_all_participants_is_topology_conflict(self):
        draft = "三个独立单元之间保留一个共同对象，用来维持整体联系。"
        message = "我不想依赖一个中心，请改用多个局部联系。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("centralized_organizer", conflicts)

    def test_multiple_local_relations_with_one_line_each_are_not_global_conflict(self):
        draft = (
            "第一处局部联系：甲与乙直接邻接，各自保留独立入口。"
            "第二处独立联系：乙与丙设置单独联系点，不经过第一处联系。"
            "第三处局部联系：丙与丁直接邻接，另设日常到达。"
            "这些联系分别发生在不同位置。"
            "可画动作：只在每一组邻接关系之间画一条短连线。"
        )
        message = "我不想依赖一个中心，请改用多个局部联系。"
        state = {
            "interaction_log": [{
                "student_message": "不要再依赖一条主线组织空间。"
            }]
        }

        conflicts = ac._rejected_route_topology_conflicts(draft, message, state)

        self.assertEqual(set(), conflicts)

    def test_affirmed_topology_after_negated_contrast_is_still_checked(self):
        draft = (
            "不采用单一大厅，也不设置贯穿路径，"
            "而是让三个独立单元围绕一个共同对象布置。"
        )
        message = "我不想依赖一个中心，请改用多个局部联系。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("centralized_organizer", conflicts)

    def test_every_participant_facing_same_referent_is_topology_conflict(self):
        draft = (
            "每个独立单元都有自己的界面，"
            "但这些界面都朝向同一个中间对象。"
        )
        message = "我不想依赖一个中心，请改用多个局部联系。"

        conflicts = ac._rejected_route_topology_conflicts(draft, message)

        self.assertIn("centralized_organizer", conflicts)

    def test_no_preset_choice_removes_imperative_choice_without_question_mark(self):
        draft = (
            "已经给出三处可以分别检验的局部联系。\n\n"
            "你可以先按自己的直觉选一个画出来，再决定是否调整。"
        )
        message = "直接给我关系，不用再让我选类型。"

        result = ac._apply_candidate_route_question_boundary(
            draft, message, {}, "design_request"
        )

        self.assertNotIn("选一个", result)
        self.assertIn("同等深度", result)

    def test_semantic_rewrite_without_distributed_relation_uses_fallback(self):
        draft = "三个组团围着一个公共空间，各入口朝向这里。"
        message = "不要中心，也别换名字绕回来。"
        renamed_again = "三个组团围出一个三岔口，所有入口都朝向这里。"

        with patch.object(ac, "_boundary_rewrite", return_value=renamed_again):
            result = ac._apply_rejected_route_topology_boundary(draft, message)

        self.assertNotIn("三岔口", result)
        self.assertIn("多个局部邻接", result)
        self.assertIn("多个联系点", result)

    def test_semantic_topology_rewrite_retries_once_for_concrete_relations(self):
        draft = "小剧场、活动室和阅览都围着一个三岔口组织。"
        message = "不要中心，也别换名字绕回来，直接给我关系。"
        first = "把三岔口缩小，三个入口仍朝向这里。"
        second = (
            "小剧场与活动室建立第一处局部联系，"
            "活动室与阅览建立第二处独立联系点。"
        )

        with patch.object(ac, "_boundary_rewrite", side_effect=[first, second]) as rewrite:
            result = ac._apply_rejected_route_topology_boundary(draft, message)

        self.assertEqual(second, result)
        self.assertEqual(2, rewrite.call_count)

    def test_topology_boundary_trace_reports_successful_rewrite(self):
        self.assertTrue(
            hasattr(ac, "_apply_rejected_route_topology_boundary_with_trace")
        )
        draft = "三个独立单元围一个共同对象。"
        message = "我不想依赖一个中心，请改用多个局部联系。"
        rewritten = (
            "第一处局部联系：甲与乙直接邻接。"
            "第二处独立联系：乙与丙另设联系点。"
        )

        with patch.object(ac, "_boundary_rewrite", return_value=rewritten):
            result, trace = ac._apply_rejected_route_topology_boundary_with_trace(
                draft, message
            )

        self.assertEqual(rewritten, result)
        self.assertEqual(
            ["centralized_organizer"], trace["topology_conflicts_before"]
        )
        self.assertTrue(trace["topology_rewrite_applied"])
        self.assertEqual([], trace["topology_conflicts_after"])
        self.assertFalse(trace["topology_fallback_used"])

    def test_topology_fallback_preserves_functions_and_drawing_action(self):
        draft = (
            "小剧场、活动室、阅览和办公室围着一个共享节点。"
            "所有入口都朝向这个节点。"
        )
        message = "不要中心，也别换名字绕回来，直接给我关系。"

        with patch.object(ac, "_boundary_rewrite", return_value="仍然围着一个路口"):
            result = ac._apply_rejected_route_topology_boundary(draft, message)

        self.assertIn("小剧场", result)
        self.assertIn("小剧场与活动室", result)
        self.assertIn("阅览与办公室", result)
        self.assertIn("活动室", result)
        self.assertIn("阅览", result)
        self.assertIn("办公室", result)
        self.assertIn("可画动作", result)
        self.assertIn("第一处局部联系", result)
        self.assertIn("第二处独立联系", result)
        self.assertIn("楼层骨架", result)
        self.assertIn("体量与剖面", result)

    def test_detected_topology_conflict_forces_complete_safe_fallback(self):
        draft = (
            "活动室、小剧场、阅览和办公室仍各自成块，保留独立入口、"
            "各自采光界面、后勤到达和楼层关系；这些设计工作都应继续保留，"
            "并落实为可以直接画出的功能方块和到达箭头。"
            "首层与二层还分别保留体量错动、局部挑空、独立楼梯和剖面采光，"
            "每个功能的开间、进深、层高与疏散距离都留作下一步验证。\n\n"
            "三个独立组仍围一个共同对象。"
        )
        message = "我不想依赖一个中心，请改用多个局部联系。"

        with patch.object(ac, "_boundary_rewrite", return_value=draft):
            result = ac._apply_rejected_route_topology_boundary(draft, message)

        self.assertIn("第一处局部联系", result)
        self.assertIn("第二处独立联系", result)
        self.assertNotIn("围一个共同对象", result)

    def test_topology_fallback_recovers_confirmed_functions_from_state(self):
        draft = "活动室、阅览和办公室又围着一个共享路口。"
        message = "不要中心，也别换名字绕回来，直接给我关系。"
        state = {
            "project": {
                "functions": {
                    "value": "活动室、阅览、小剧场、办公室",
                }
            }
        }

        with patch.object(ac, "_boundary_rewrite", return_value="仍然围着一个路口"):
            result = ac._apply_rejected_route_topology_boundary(
                draft, message, state
            )

        self.assertIn("小剧场", result)

    def test_topology_fallback_deduplicates_contained_function_aliases(self):
        draft = (
            "小剧场、活动室、阅览区和办公室各自成块。"
            "三个组仍围一个共同对象，阅览需要安静。"
        )
        message = "不要中心，也别换名字绕回来，直接给我关系。"

        with patch.object(ac, "_boundary_rewrite", return_value=draft):
            result = ac._apply_rejected_route_topology_boundary(draft, message)

        self.assertIn("办公室", result)
        self.assertNotIn("阅览区与阅览", result)
        self.assertIn("阅览区与办公室", result)

    def test_independent_entrances_do_not_prove_distributed_connections(self):
        draft = (
            "四个功能各自有独立入口。"
            "四个块都用一条很短的连接串起来，所有门都开向同一条短连接。"
        )
        message = "不要中心或一条街，也别换名字绕回来。"
        state = {
            "project": {
                "functions": {
                    "value": "小剧场、活动室、阅览、办公室",
                }
            }
        }

        self.assertFalse(ac._has_distributed_relation_evidence(draft))
        with patch.object(ac, "_boundary_rewrite", return_value=draft):
            result = ac._apply_rejected_route_topology_boundary(
                draft, message, state
            )

        self.assertNotIn("同一条短连接", result)
        self.assertIn("第一处局部联系", result)
        self.assertIn("第二处独立联系", result)

    def test_rejected_linear_topology_cannot_return_as_short_passage(self):
        draft = (
            "四个独立块排成两排，中间留一条短而宽的连接带。"
            "四个区的门都开向连接带，楼梯也放在连接带中段。"
        )
        message = "线性和一条街我都不要，不要换成短通道继续串所有功能。"
        rewritten = (
            "四个功能块形成两组邻接单元，两组之间设置两个独立联系点。"
            "没有一条所有功能共同依赖的主通道。"
        )

        with patch.object(ac, "_boundary_rewrite", return_value=rewritten) as rewrite:
            result = ac._apply_rejected_route_topology_boundary(draft, message)

        self.assertEqual(rewritten, result)
        rewrite.assert_called_once()
        self.assertNotIn("都开向连接带", result)

    def test_prior_turn_linear_rejection_remains_active(self):
        draft = (
            "三个组团各自独立成块，彼此之间用一条很轻的连接串起来。"
            "三个组团都通过这条短廊到达。"
        )
        message = "按我说的各自独立但别太散重新想，直接给我关系。"
        state = {
            "interaction_log": [{
                "turn_id": 5,
                "student_message": "线性像学校走廊，我不喜欢，不要靠一条街串所有功能。",
                "ai_reply": "可以换一种组织。",
            }]
        }
        rewritten = (
            "三个组团以两组邻接关系和两个到达点联系，"
            "没有所有组团共同依赖的连接线。"
        )

        with patch.object(ac, "_boundary_rewrite", return_value=rewritten) as rewrite:
            result = ac._apply_rejected_route_topology_boundary(
                draft, message, state
            )

        self.assertEqual(rewritten, result)
        rewrite.assert_called_once()

    def test_current_explicit_confirmation_overrides_old_route_rejection(self):
        draft = "三个组团沿一条室内街道展开，入口和楼梯都接入这条街。"
        message = "我决定采用线性街道，就按这个方案继续深化。"
        state = {
            "interaction_log": [{
                "turn_id": 5,
                "student_message": "之前我不喜欢线性，不要靠一条街。",
                "ai_reply": "先换一个方向。",
            }]
        }

        with patch.object(ac, "_boundary_rewrite") as rewrite:
            result = ac._apply_rejected_route_topology_boundary(
                draft, message, state
            )

        self.assertEqual(draft, result)
        rewrite.assert_not_called()

    def test_distributed_local_connections_do_not_trigger_topology_rewrite(self):
        draft = (
            "活动室与手工区直接相邻，阅览区与室外平台形成另一组。"
            "两组之间设置两个短连接点，不依赖共同中心或单一主通道。"
        )
        message = "不要中心，也不要一条街，我想各自独立但别太散。"

        with patch.object(ac, "_boundary_rewrite") as rewrite:
            result = ac._apply_rejected_route_topology_boundary(draft, message)

        self.assertEqual(draft, result)
        rewrite.assert_not_called()


if __name__ == "__main__":
    unittest.main()
