import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import architect_chat as ac


class ExperiencePatchExecutionTests(unittest.TestCase):
    def _response(self, content: str) -> Mock:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"choices": [{"message": {"content": content}}]}
        return response

    def test_checker_requires_sentence_level_identity_judgment(self):
        self.assertIn("逐句检查", ac._EXPERIENCE_PATCH_INSTRUCTION)
        self.assertIn("后文", ac._EXPERIENCE_PATCH_INSTRUCTION)
        self.assertIn("不能抵消", ac._EXPERIENCE_PATCH_INSTRUCTION)
        self.assertIn("目标不等于实现方法", ac._EXPERIENCE_PATCH_INSTRUCTION)
        self.assertIn("直接决定", ac._EXPERIENCE_PATCH_INSTRUCTION)
        self.assertIn("枢纽", ac._EXPERIENCE_PATCH_INSTRUCTION)

    def test_patch_output_budget_scales_with_candidate_count(self):
        self.assertGreaterEqual(ac._experience_patch_max_tokens(2), 1400)
        self.assertGreater(ac._experience_patch_max_tokens(20), ac._experience_patch_max_tokens(2))
        self.assertLessEqual(ac._experience_patch_max_tokens(20), 4000)

    def test_recall_finds_deterministic_experience_candidates(self):
        draft = (
            "北侧临城市道路，这是主要到达界面，人流大概率从北侧来。\n"
            "主入口放北侧，面向城市道路。\n"
            "室外场地通常直接贴靠班级单元。\n"
            "可以把中庭作为一个候选方向。\n"
            "舞蹈教室不能放在二层。"
        )

        candidates = ac._recall_experience_assertion_candidates(draft)

        self.assertIn("北侧临城市道路，这是主要到达界面，人流大概率从北侧来。", candidates)
        self.assertIn("主入口放北侧，面向城市道路。", candidates)
        self.assertIn("室外场地通常直接贴靠班级单元。", candidates)
        self.assertIn("舞蹈教室不能放在二层。", candidates)
        self.assertNotIn("可以把中庭作为一个候选方向。", candidates)

    def test_recall_finds_site_experience_without_modal_words(self):
        draft = (
            "- **南侧边界开敞** → 可承接主要到达与公共活动，适合放入口和公共性强的功能。\n"
            "- **北侧临现有建筑** → 是既有界面，适合放需要安静的后勤功能。"
        )

        candidates = ac._recall_experience_assertion_candidates(draft)

        self.assertIn(
            "- **南侧边界开敞** → 可承接主要到达与公共活动，适合放入口和公共性强的功能。",
            candidates,
        )
        self.assertIn(
            "- **北侧临现有建筑** → 是既有界面，适合放需要安静的后勤功能。",
            candidates,
        )

    def test_recall_finds_type_rule_embedded_in_bold_lead(self):
        draft = (
            "2. **寝室与室外场地不直接相连**。"
            "寝室可以考虑通过活动室间接到达室外，具体关系需要结合声环境验证。"
        )

        candidates = ac._recall_experience_assertion_candidates(draft)

        self.assertIn("2. **寝室与室外场地不直接相连**。", candidates)

    def test_recall_finds_real_kindergarten_rule_variants(self):
        draft = (
            "每个班是一个独立单元，包含活动室、寝室和卫生间。\n"
            "关键关系：寝室不直接对室外，活动室直接对室外。\n"
            "班级专属场地紧贴每个班的活动室。"
        )

        candidates = ac._recall_experience_assertion_candidates(draft)

        self.assertIn("每个班是一个独立单元，包含活动室、寝室和卫生间。", candidates)
        self.assertIn("关键关系：寝室不直接对室外，活动室直接对室外。", candidates)
        self.assertIn("班级专属场地紧贴每个班的活动室。", candidates)

    def test_site_and_type_lead_patches_preserve_the_design_body(self):
        draft = (
            "- **南侧边界开敞** → 可承接主要到达与公共活动，适合放入口和公共性强的功能。\n"
            "2. **寝室与室外场地不直接相连**。\n"
            "可画动作：保留入口、活动室、寝室和室外场地四个块。"
        )
        payload = {
            "patches": [
                {
                    "original_text": "- **南侧边界开敞** → 可承接主要到达与公共活动，适合放入口和公共性强的功能。",
                    "issue_type": "missing_condition",
                    "missing_condition": "主要到达方向和功能开放性",
                    "replacement_text": "- **南侧边界开敞** → 如果主要到达方向与开放条件成立，可以把南侧入口作为候选。",
                },
                {
                    "original_text": "2. **寝室与室外场地不直接相连**。",
                    "issue_type": "project_factification",
                    "missing_condition": "声环境、管理和过渡空间条件",
                    "replacement_text": "2. **寝室与室外场地关系候选**：可以先比较直接连接与间接连接，再结合声环境和管理条件验证。",
                },
            ]
        }

        result = ac._apply_experience_patches(draft, payload)

        self.assertIn("如果主要到达方向与开放条件成立", result)
        self.assertIn("可以先比较直接连接与间接连接", result)
        self.assertIn("可画动作：保留入口、活动室、寝室和室外场地四个块。", result)
        self.assertNotIn("适合放入口", result)
        self.assertNotIn("寝室与室外场地不直接相连", result)

    def test_review_contract_requires_a_verdict_for_every_candidate(self):
        candidates = ["北侧道路决定主入口。", "可以保留中庭。"]
        incomplete = {
            "reviews": [
                {"candidate_id": "C1", "verdict": "safe"},
            ]
        }

        self.assertIsNone(ac._experience_reviews_to_patch_payload(incomplete, candidates))

    def test_review_contract_converts_patch_verdict(self):
        candidates = ["北侧道路决定主入口。", "舞蹈教室不能放二层。"]
        payload = {
            "reviews": [
                {"candidate_id": "C1", "verdict": "safe"},
                {
                    "candidate_id": "C2",
                    "verdict": "patch",
                    "original_text": "舞蹈教室不能放二层。",
                    "issue_type": "missing_condition",
                    "missing_condition": "振动、结构和隔振条件",
                    "replacement_text": "舞蹈教室放二层时，需要结合振动、结构和隔振条件验证。",
                },
            ]
        }

        self.assertEqual(
            {
                "patches": [
                    {
                        "original_text": "舞蹈教室不能放二层。",
                        "issue_type": "missing_condition",
                        "missing_condition": "振动、结构和隔振条件",
                        "replacement_text": "舞蹈教室放二层时，需要结合振动、结构和隔振条件验证。",
                    }
                ]
            },
            ac._experience_reviews_to_patch_payload(payload, candidates),
        )

    def test_recalled_candidate_can_trigger_check_when_design_gate_misses_turn(self):
        old_enabled = ac.ENABLE_EXPERIENCE_PATCH_EXECUTION
        try:
            ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = True
            self.assertTrue(
                ac._should_run_preoutput_check(
                    "general_advice",
                    "请推活动室、寝室和室外关系。",
                    "活动室和寝室必须紧邻。",
                )
            )
            self.assertFalse(
                ac._should_run_preoutput_check(
                    "general_advice",
                    "解释一下这个概念。",
                    "可以把中庭作为一个候选方向。",
                )
            )
        finally:
            ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old_enabled

    def test_applies_exact_local_patch_and_preserves_design_labor(self):
        draft = (
            "首层设置社区共享大厅，并串联展览与咖啡。\n"
            "北侧临城市道路，所以主入口应该放在北侧。\n"
            "二层以环廊连接教室，可画出两层流线。"
        )
        result = ac._apply_experience_patches(
            draft,
            {
                "patches": [
                    {
                        "original_text": "北侧临城市道路，所以主入口应该放在北侧。",
                        "issue_type": "project_factification",
                        "missing_condition": "主要到达方向、道路等级和开口条件",
                        "replacement_text": (
                            "如果北侧承担主要到达，可以把北侧入口作为候选，"
                            "并结合道路等级和开口条件验证。"
                        ),
                    }
                ]
            },
        )

        self.assertIn("首层设置社区共享大厅，并串联展览与咖啡。", result)
        self.assertIn("如果北侧承担主要到达，可以把北侧入口作为候选", result)
        self.assertIn("二层以环廊连接教室，可画出两层流线。", result)
        self.assertNotIn("主入口应该放在北侧", result)

    def test_rejects_patch_when_original_text_does_not_match(self):
        draft = "南侧设置连续公共空间。"
        result = ac._apply_experience_patches(
            draft,
            {
                "patches": [
                    {
                        "original_text": "南侧应该设置连续公共空间。",
                        "issue_type": "missing_condition",
                        "missing_condition": "日照和开放条件",
                        "replacement_text": "如果开放条件成立，可考虑南侧公共空间。",
                    }
                ]
            },
        )

        self.assertEqual(draft, result)

    def test_rejects_invalid_or_incomplete_payload(self):
        draft = "活动室最好都有独立出口。"

        self.assertEqual(draft, ac._apply_experience_patches(draft, {"patches": "bad"}))
        self.assertEqual(
            draft,
            ac._apply_experience_patches(
                draft,
                {
                    "patches": [
                        {
                            "original_text": draft,
                            "issue_type": "project_factification",
                            "replacement_text": "可比较独立出口与共享出口。",
                        }
                    ]
                },
            ),
        )

    def test_rejects_replacement_that_keeps_deterministic_assertion(self):
        draft = "北侧道路决定主入口。"
        result = ac._apply_experience_patches(
            draft,
            {
                "patches": [
                    {
                        "original_text": draft,
                        "issue_type": "project_factification",
                        "missing_condition": "主要到达方向",
                        "replacement_text": "北侧主入口是最佳选择。",
                    }
                ]
            },
        )

        self.assertEqual(draft, result)

    def test_accepts_common_conditional_rewrite_variants(self):
        cases = (
            (
                "西侧住宅决定安静功能布局。",
                "西侧与住宅的关系应结合距离、开口和实际噪声评估后再确定功能布局。",
            ),
            (
                "北侧道路决定主入口。",
                "在主要到达方向明确后，可将北侧入口作为一个测试位置。",
            ),
            (
                "儿童活动必须靠近室外。",
                "儿童活动与室外的关系需确认管理、看护和场地边界条件后再确定。",
            ),
        )

        for draft, replacement in cases:
            with self.subTest(replacement=replacement):
                result = ac._apply_experience_patches(
                    draft,
                    {
                        "patches": [{
                            "original_text": draft,
                            "issue_type": "missing_condition",
                            "missing_condition": "项目实际条件",
                            "replacement_text": replacement,
                        }]
                    },
                )
                self.assertEqual(replacement, result)

    def test_plain_suggestion_word_does_not_make_assertion_conditional(self):
        draft = "北侧道路决定主入口。"

        result = ac._apply_experience_patches(
            draft,
            {
                "patches": [{
                    "original_text": draft,
                    "issue_type": "missing_condition",
                    "missing_condition": "主要到达方向",
                    "replacement_text": "建议主入口确定放在北侧。",
                }]
            },
        )

        self.assertEqual(draft, result)

    def test_invalid_patch_does_not_block_valid_sibling_patch(self):
        draft = "北侧道路决定主入口。舞蹈教室不能放二层。"
        result = ac._apply_experience_patches(
            draft,
            {
                "patches": [
                    {
                        "original_text": "北侧道路决定主入口。",
                        "issue_type": "missing_condition",
                        "missing_condition": "主要到达方向",
                        "replacement_text": "如果北侧承担主要到达，可以把北侧入口作为候选。",
                    },
                    {
                        "original_text": "舞蹈教室不能放二层。",
                        "issue_type": "project_factification",
                        "missing_condition": "结构和振动条件",
                        "replacement_text": "舞蹈教室必须放一层。",
                    },
                ]
            },
        )

        self.assertEqual(
            "如果北侧承担主要到达，可以把北侧入口作为候选。舞蹈教室不能放二层。",
            result,
        )

    def test_applies_more_than_eight_valid_sentence_patches(self):
        originals = [f"经验句{i}必须采用固定关系。" for i in range(1, 10)]
        draft = "".join(originals)
        payload = {
            "patches": [
                {
                    "original_text": original,
                    "issue_type": "project_factification",
                    "missing_condition": "项目条件",
                    "replacement_text": f"经验句{i}可以作为候选关系，需要结合项目条件验证。",
                }
                for i, original in enumerate(originals, start=1)
            ]
        }

        result = ac._apply_experience_patches(draft, payload)

        self.assertNotEqual(draft, result)
        self.assertEqual(9, result.count("需要结合项目条件验证"))

    def test_parses_json_from_markdown_fence(self):
        payload = ac._parse_experience_patch_payload(
            '```json\n{"patches": []}\n```'
        )

        self.assertEqual({"patches": []}, payload)

    def test_parses_json_object_while_ignoring_checker_prose(self):
        payload = ac._parse_experience_patch_payload(
            '检查完成。\n{"patches": []}\n以上为内部结果。'
        )

        self.assertEqual({"patches": []}, payload)

    def test_parses_current_review_contract_while_ignoring_checker_prose(self):
        payload = ac._parse_experience_patch_payload(
            '判断如下。\n{"reviews":[{"candidate_id":"C1","verdict":"safe"}]}\n结束。'
        )

        self.assertEqual(
            {"reviews": [{"candidate_id": "C1", "verdict": "safe"}]},
            payload,
        )

    def test_hidden_check_retries_invalid_json_then_applies_valid_patch(self):
        draft = "儿童活动区最好都有独立出口。"
        valid = (
            '{"reviews":[{'
            '"candidate_id":"C1",'
            '"verdict":"patch",'
            '"original_text":"儿童活动区最好都有独立出口。",'
            '"issue_type":"missing_condition",'
            '"missing_condition":"看护、场地边界和流线条件",'
            '"replacement_text":"如果直接联系室外是目标，可以比较独立出口与共享出口。"'
            '}]} '
        )
        old_key = ac.DEEPSEEK_API_KEY
        old_enabled = ac.ENABLE_EXPERIENCE_PATCH_EXECUTION
        try:
            ac.DEEPSEEK_API_KEY = "test-key"
            ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = True
            with patch(
                "architect_chat.requests.post",
                side_effect=[self._response("不是 JSON"), self._response(valid)],
            ) as mocked_post:
                result = ac._hidden_check_revise(draft, {}, "test policy")
        finally:
            ac.DEEPSEEK_API_KEY = old_key
            ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old_enabled

        self.assertEqual("如果直接联系室外是目标，可以比较独立出口与共享出口。", result)
        self.assertEqual(2, mocked_post.call_count)

    def test_hidden_check_falls_back_after_two_invalid_payloads(self):
        draft = "舞蹈教室不能放二层。"
        old_key = ac.DEEPSEEK_API_KEY
        old_enabled = ac.ENABLE_EXPERIENCE_PATCH_EXECUTION
        try:
            ac.DEEPSEEK_API_KEY = "test-key"
            ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = True
            with patch(
                "architect_chat.requests.post",
                side_effect=[self._response("内部检查结果"), self._response("仍然不是 JSON")],
            ) as mocked_post:
                result = ac._hidden_check_revise(draft, {}, "test policy")
        finally:
            ac.DEEPSEEK_API_KEY = old_key
            ac.ENABLE_EXPERIENCE_PATCH_EXECUTION = old_enabled

        self.assertEqual(draft, result)
        self.assertEqual(2, mocked_post.call_count)

    def test_applies_multiple_patches_without_changing_intermediate_text(self):
        draft = "北侧道路决定主入口。中庭组织保持不变。舞蹈教室不能放二层。"
        result = ac._apply_experience_patches(
            draft,
            {
                "patches": [
                    {
                        "original_text": "北侧道路决定主入口。",
                        "issue_type": "project_factification",
                        "missing_condition": "主要到达方向",
                        "replacement_text": "如果主要到达来自北侧，可把北侧入口作为候选。",
                    },
                    {
                        "original_text": "舞蹈教室不能放二层。",
                        "issue_type": "missing_condition",
                        "missing_condition": "结构振动和隔振条件",
                        "replacement_text": "舞蹈教室放二层时，需要结合结构振动和隔振条件验证。",
                    },
                ]
            },
        )

        self.assertEqual(
            "如果主要到达来自北侧，可把北侧入口作为候选。"
            "中庭组织保持不变。"
            "舞蹈教室放二层时，需要结合结构振动和隔振条件验证。",
            result,
        )

    def test_recall_catches_absolute_comparison_as_experience_candidate(self):
        draft = "这条动静轴线比入口更根本。"

        candidates = ac._recall_experience_assertion_candidates(draft)

        self.assertEqual([draft], candidates)

    def test_recall_catches_unconditional_function_placement(self):
        draft = "热闹侧靠入口，安静侧靠深处。"

        candidates = ac._recall_experience_assertion_candidates(draft)

        self.assertEqual([draft], candidates)

    def test_recall_catches_route_superiority_wording(self):
        draft = "两条流线比一条主轴更稳，也更贴近这些功能的实际使用方式。"

        candidates = ac._recall_experience_assertion_candidates(draft)

        self.assertEqual([draft], candidates)

    def test_recall_catches_unverified_hard_constraint_wording(self):
        draft = "小剧场需要独立出入口和独立疏散，这是功能硬约束。"

        candidates = ac._recall_experience_assertion_candidates(draft)

        self.assertEqual([draft], candidates)

    def test_recall_catches_site_condition_assigned_as_design_role(self):
        drafts = (
            "东侧公园是场地的主要景观资源，西侧住宅构成私密性约束。",
            "北侧道路承担主要到达，东侧绿地承担公共开放界面。",
            "住宅侧安排安静功能，公园侧布置儿童活动空间。",
        )

        for draft in drafts:
            with self.subTest(draft=draft):
                self.assertEqual(
                    [draft],
                    ac._recall_experience_assertion_candidates(draft),
                )

    def test_recall_does_not_treat_plain_site_fact_as_design_role(self):
        draft = "基地北侧有道路，东侧有公园，西侧有住宅。"

        candidates = ac._recall_experience_assertion_candidates(draft)

        self.assertEqual([], candidates)

    def test_checker_explicitly_reviews_unconfirmed_site_role_assignment(self):
        self.assertIn("分配设计角色", ac._EXPERIENCE_PATCH_INSTRUCTION)
        self.assertIn("景观资源", ac._EXPERIENCE_PATCH_INSTRUCTION)
        self.assertIn("用户已经确认", ac._EXPERIENCE_PATCH_INSTRUCTION)

    def test_checker_reviews_unsupported_engineering_details_and_rankings(self):
        self.assertIn("具体构造节点", ac._EXPERIENCE_PATCH_INSTRUCTION)
        self.assertIn("性能排序", ac._EXPERIENCE_PATCH_INSTRUCTION)

        draft = (
            "舞蹈教室楼板通过弹性支座与主体脱开，形成房中房式浮筑楼板。"
            "厚板加弹性面层的隔振效果中等，结构脱开的效果更彻底。"
        )
        candidates = ac._recall_experience_assertion_candidates(draft)

        self.assertIn(
            "舞蹈教室楼板通过弹性支座与主体脱开，形成房中房式浮筑楼板。",
            candidates,
        )
        self.assertIn(
            "厚板加弹性面层的隔振效果中等，结构脱开的效果更彻底。",
            candidates,
        )

    def test_site_role_fallback_conditions_residual_role_assertions(self):
        draft = (
            "东边公园是场地里明确的景观资源。"
            "北侧道路承担主要到达。"
            "西侧住宅是场地的安静边界。"
            "公园是场地里明确的资源。"
            "西侧住宅需要被遮挡。"
            "两套空间骨架和可画动作保持不变。"
        )

        result = ac._apply_site_role_fallback(draft)

        self.assertNotIn("明确的景观资源", result)
        self.assertNotIn("道路承担主要到达", result)
        self.assertNotIn("住宅是场地的安静边界", result)
        self.assertNotIn("公园是场地里明确的资源", result)
        self.assertNotIn("住宅需要被遮挡", result)
        self.assertIn("能否成为主要景观资源", result)
        self.assertIn("是否承担主要到达", result)
        self.assertIn("是否需要形成安静或缓冲边界", result)
        self.assertIn("两套空间骨架和可画动作保持不变", result)

    def test_site_role_fallback_preserves_plain_site_facts(self):
        draft = "基地北侧有道路，东侧有公园，西侧有住宅。"

        self.assertEqual(draft, ac._apply_site_role_fallback(draft))

    def test_recall_catches_unpunctuated_markdown_bullets(self):
        draft = (
            "- 入口放在北侧小路，进门后进入公共空间\n"
            "- 东侧靠公园布置阅览和茶室\n"
            "- 西侧靠住宅布置服务功能作为缓冲\n"
            "- 两套方案都可修改"
        )

        candidates = ac._recall_experience_assertion_candidates(draft)

        self.assertIn("- 入口放在北侧小路，进门后进入公共空间", candidates)
        self.assertGreaterEqual(len(candidates), 1)

    def test_recall_catches_source_first_site_role_assignments(self):
        draft = (
            "- 北侧临社区路放主入口和门厅\n"
            "- 西侧挨住宅放安静功能，东侧靠绿地放活跃功能\n"
            "- 主入口直接面对社区路，绿地作为视觉延伸和户外活动场地\n"
            "- 入口与组织方式仍然没有确定"
        )

        candidates = ac._recall_experience_assertion_candidates(draft)

        self.assertIn("- 北侧临社区路放主入口和门厅", candidates)
        self.assertIn("- 西侧挨住宅放安静功能，东侧靠绿地放活跃功能", candidates)
        self.assertIn("- 主入口直接面对社区路，绿地作为视觉延伸和户外活动场地", candidates)

    def test_site_role_fallback_conditions_parenthetical_fact_labels(self):
        draft = "- 东：公园（景观资源）\n- 西：住宅（噪声/私密敏感）"

        result = ac._apply_site_role_fallback(draft)

        self.assertNotIn("公园（景观资源）", result)
        self.assertNotIn("住宅（噪声/私密敏感）", result)
        self.assertIn("需验证", result)

    def test_site_role_fallback_conditions_arrival_interface_label(self):
        draft = "- 北侧临社区道路（目前唯一明确的到达界面）\n北侧是唯一明确到达面。"

        result = ac._apply_site_role_fallback(draft)

        self.assertNotIn("唯一明确的到达界面", result)
        self.assertNotIn("唯一明确到达面", result)
        self.assertIn("是否构成主要到达界面", result)

    def test_engineering_fallback_does_not_treat_function_buffer_as_proof(self):
        draft = (
            "如果舞蹈教室下方是门厅或库房，二层的振动和声音基本不构成问题，"
            "不需要额外构造。仍可比较三种剖面处理。"
        )

        result = ac._apply_site_role_fallback(draft)

        self.assertNotIn("基本不构成问题", result)
        self.assertNotIn("不需要额外构造", result)
        self.assertIn("不能据此确认", result)
        self.assertIn("楼板振动", result)
        self.assertIn("仍可比较三种剖面处理", result)

    def test_engineering_fallback_does_not_promise_floating_floor_performance(self):
        draft = (
            "如果楼下是门厅，振动问题基本不成立。"
            "二层舞蹈教室可加弹性垫层（浮筑），把振动和主体结构隔开，楼下不受影响。"
            "剖面画一条弹性垫层线，楼板与梁之间留出空隙。"
            "如果楼下不敏感，浮筑就可以省掉，只做大跨即可。"
            "仍然保留功能错位和减振构造两个剖面候选。"
        )

        result = ac._apply_site_role_fallback(draft)

        self.assertNotIn("振动问题基本不成立", result)
        self.assertNotIn("把振动和主体结构隔开，楼下不受影响", result)
        self.assertNotIn("楼板与梁之间留出空隙", result)
        self.assertNotIn("只做大跨即可", result)
        self.assertIn("不能据此确认楼板振动满足要求", result)
        self.assertIn("不能预设楼下不受影响", result)
        self.assertIn("结构体系", result)
        self.assertIn("仍然保留功能错位和减振构造两个剖面候选", result)

    def test_engineering_fallback_separates_airborne_sound_from_floor_vibration(self):
        draft = (
            "这层夹心把舞蹈的撞击振动吸收掉，不往下传。"
            "这是空间错位加构造隔声的组合，不依赖浮筑也能明显降噪。"
            "把这两个剖面各画一个 1:50 的局部大样，先标构造层。"
            "仍保留浮筑系统和空间错位两个剖面研究方向。"
        )

        result = ac._apply_site_role_fallback(draft)

        self.assertNotIn("吸收掉，不往下传", result)
        self.assertNotIn("不依赖浮筑也能明显降噪", result)
        self.assertNotIn("1:50 的局部大样", result)
        self.assertIn("结构振动", result)
        self.assertIn("空气声", result)
        self.assertIn("剖面概念草图", result)
        self.assertIn("仍保留浮筑系统和空间错位两个剖面研究方向", result)


if __name__ == "__main__":
    unittest.main()
