import unittest
from unittest.mock import patch

from direction_proposer import (
    _directions_match_project,
    _fallback_directions,
    _grounded_fallback_directions,
    _validate_direction_evidence,
    _verified_evidence,
)
from design_discussion import ask_next_question, assess_understanding


class FallbackDirectionsTests(unittest.TestCase):
    def test_fallback_directions_have_display_fields(self):
        result = _fallback_directions([])

        self.assertEqual(3, len(result["directions"]))
        for direction in result["directions"]:
            self.assertTrue(direction["core_strategy"])
            self.assertTrue(direction["suitable_for"])
            self.assertTrue(direction["risk"])

    def test_rural_house_fallback_directions_remain_residential(self):
        result = _fallback_directions([], "乡村独立住宅，200平米，在农村平原路边")
        names = " ".join(direction["name"] for direction in result["directions"])

        self.assertIn("院落", names)
        self.assertNotIn("校园", names)

    def test_office_fallback_directions_remain_office_specific(self):
        result = _fallback_directions([], "我想设计一座办公楼，位于城市主干道旁")
        content = " ".join(
            [result["core_conflict"]]
            + [direction["name"] + direction["core_strategy"] for direction in result["directions"]]
        )

        self.assertIn("办公", content)
        self.assertNotIn("学生", content)
        self.assertNotIn("校园", content)

    def test_rejects_directions_that_do_not_match_the_current_project_type(self):
        generic_directions = [
            {"name": "空间体验型", "core_strategy": "为学生设计停留与交流空间"},
            {"name": "开放共享型", "core_strategy": "组织校园节点的人流"},
            {"name": "自然融合型", "core_strategy": "为展馆引入光和庭院"},
        ]

        self.assertFalse(_directions_match_project(generic_directions, "乡村民宿"))

    def test_rejects_hallucinated_knowledge_reference(self):
        directions = [{
            "name": "场地回应型",
            "evidence": {
                "case": {"name": "不存在的案例", "why": "虚构引用"},
                "theory": {"name": "场所精神", "why": "回应场地"},
                "method": {"name": "框景借景", "why": "组织视线"},
            },
        }]
        cases = [{"name": "萨伏伊别墅", "strategy": "自由平面"}]
        theories = [{"name": "场所精神"}]
        methods = [{"name": "框景借景"}]

        self.assertFalse(_validate_direction_evidence(directions, cases, theories, methods))

    def test_accepts_evidence_from_the_retrieved_knowledge_only(self):
        directions = [{
            "name": "场地回应型",
            "evidence": {
                "case": {"name": "萨伏伊别墅", "why": "借鉴自由平面的组织方式"},
                "theory": {"name": "场所精神", "why": "回应场地"},
                "method": {"name": "框景借景", "why": "组织视线"},
            },
        }]
        cases = [{"name": "萨伏伊别墅", "strategy": "自由平面"}]
        theories = [{"name": "场所精神"}]
        methods = [{"name": "框景借景"}]

        self.assertTrue(_validate_direction_evidence(directions, cases, theories, methods))

    def test_verified_evidence_uses_complete_local_source_text(self):
        direction = {
            "name": "场地回应型",
            "evidence": {
                "case": {"name": "萨伏伊别墅", "why": "用于组织公共空间"},
                "theory": {"name": "场所精神", "why": "回应村庄环境"},
                "method": {"name": "框景借景", "why": "引入田野视线"},
            },
        }
        cases = [{"name": "萨伏伊别墅", "strategy": "自由平面", "content": "原建筑以结构柱网释放内部隔墙。"}]
        theories = [{"name": "场所精神", "content": "建筑应识别并回应场地的具体特征。"}]
        methods = [{"name": "框景借景", "content": "通过开口控制视域并将外部景观纳入空间。"}]

        result = _verified_evidence(direction, cases, theories, methods)

        self.assertEqual(cases[0]["content"], result["evidence"]["case"]["source_text"])
        self.assertEqual(theories[0]["content"], result["evidence"]["theory"]["source_text"])
        self.assertEqual(methods[0]["content"], result["evidence"]["method"]["source_text"])

    def test_grounded_fallback_binds_every_direction_to_retrieved_sources(self):
        cases = [{"name": "萨伏伊别墅", "strategy": "自由平面"}]
        theories = [{"name": "场所精神"}]
        methods = [{"name": "框景借景"}]

        result = _grounded_fallback_directions(
            cases, theories, methods, "乡村民宿", "乡村民宿", {"site": "农村路边"}
        )

        self.assertEqual("partial", result["knowledge_note"]["status"])
        self.assertTrue(_validate_direction_evidence(result["directions"], cases, theories, methods))

    @patch("design_discussion._call_llm", return_value={})
    def test_discussion_returns_a_clear_fallback_question_when_model_has_no_result(self, _mock_call):
        result = ask_next_question("设计一个校园交流中心", ["设计一个校园交流中心"], {})

        self.assertTrue(result["need_more"])
        self.assertEqual("project_type", result["dimension"])
        self.assertTrue(result["question"])
        self.assertTrue(result["fallback"])

    @patch(
        "design_discussion._call_llm",
        return_value={"project_type": "", "user": "", "site": "", "goal": "", "constraint": ""},
    )
    def test_discussion_fallback_preserves_a_rural_house_brief(self, _mock_call):
        brief = "乡村独立住宅，200平米，在农村，平原，路边"
        understanding = assess_understanding(brief, [brief])
        question = ask_next_question(brief, [brief], understanding)

        self.assertEqual("乡村独立住宅", understanding["project_type"])
        self.assertIn("农村", understanding["site"])
        self.assertIn("200", understanding["constraint"])
        self.assertEqual("user", question["dimension"])
        self.assertNotIn("校园", " ".join(question["options"]))

    @patch("design_discussion._call_llm", return_value={})
    def test_discussion_fallback_understands_an_office_building(self, _mock_call):
        brief = "我想设计一座办公楼，位于城市主干道旁"
        understanding = assess_understanding(brief, [brief])
        question = ask_next_question(brief, [brief], understanding)

        self.assertEqual("办公楼", understanding["project_type"])
        self.assertEqual("user", question["dimension"])
        self.assertIn("办公", " ".join(question["options"]))
        self.assertNotIn("校园", " ".join(question["options"]))

    @patch("design_discussion._call_llm", return_value={})
    def test_confirmed_answer_advances_discussion_to_the_next_dimension(self, _mock_call):
        brief = "我想设计一座办公楼，位于城市主干道旁"
        facts = {"使用者": ""}
        understanding = assess_understanding(
            brief,
            [brief, "办公、会议和展示并重"],
            known_facts={"user": "办公、会议和展示并重"},
        )
        question = ask_next_question(brief, [brief], understanding)

        self.assertEqual("办公、会议和展示并重", understanding["user"])
        self.assertEqual(50, understanding["understanding_percent"])
        self.assertEqual("goal", question["dimension"])

    @patch("design_discussion._call_llm", return_value={})
    def test_complete_confirmed_facts_stop_the_question_loop(self, _mock_call):
        understanding = assess_understanding(
            "设计一座办公楼",
            ["设计一座办公楼"],
            known_facts={
                "project_type": "办公楼",
                "user": "办公、会议和展示并重",
                "site": "城市主干道旁",
                "goal": "提升协作效率",
                "constraint": "控制建设成本",
                "design_intent": "形成克制而有识别度的工作场所",
            },
        )
        question = ask_next_question("设计一座办公楼", [], understanding)

        self.assertEqual(100, understanding["understanding_percent"])
        self.assertFalse(question["need_more"])

    @patch("design_discussion._call_llm", return_value={})
    def test_every_project_requires_a_design_intent_before_directions(self, _mock_call):
        for project_type in ["乡村民宿", "写字楼", "城市广场"]:
            understanding = assess_understanding(
                project_type,
                [project_type],
                known_facts={
                    "project_type": project_type,
                    "user": "周末休闲的城市住客",
                    "site": "项目场地",
                    "goal": "完成核心使用目标",
                    "constraint": "控制建设成本",
                },
            )
            question = ask_next_question(project_type, [], understanding)

            self.assertEqual(5, len([item for item in understanding["filled_dimensions"] if item["value"]]))
            self.assertEqual("design_intent", question["dimension"])
            self.assertTrue(question["need_more"])

    @patch(
        "design_discussion._call_llm",
        return_value={
            "project_type": "乡村民宿",
            "user": "城市游客",
            "site": "乡村场地",
            "goal": "休闲度假",
            "constraint": "控制成本",
            "design_intent": "自然放松",
        },
    )
    def test_model_guesses_do_not_count_as_confirmed_understanding(self, _mock_call):
        understanding = assess_understanding("乡村民宿", ["乡村民宿"])

        self.assertEqual(17, understanding["understanding_percent"])
        self.assertEqual("乡村民宿", understanding["project_type"])
        self.assertEqual("", understanding["user"])
        self.assertEqual("", understanding["site"])
        self.assertEqual("", understanding["goal"])
        self.assertEqual("", understanding["constraint"])

    @patch("design_discussion._call_llm", return_value={})
    def test_progress_uses_confirmed_facts_and_never_drops_after_an_answer(self, _mock_call):
        first = assess_understanding("乡村民宿", ["乡村民宿"])
        second = assess_understanding(
            "乡村民宿",
            ["乡村民宿", "主要面向周末休闲的城市家庭"],
            known_facts={"user": "主要面向周末休闲的城市家庭"},
        )

        self.assertEqual(17, first["understanding_percent"])
        self.assertEqual(33, second["understanding_percent"])
        self.assertGreaterEqual(second["understanding_percent"], first["understanding_percent"])

    @patch(
        "design_discussion._call_llm",
        side_effect=[
            {"need_more": True, "dimension": "user", "question": "主要给谁使用？", "options": ["家庭", "游客"]},
            {"need_more": True, "dimension": "user", "question": "住客通常会停留多久？", "options": ["周末", "长住"]},
        ],
    )
    def test_dynamic_question_avoids_repeating_a_previous_question(self, _mock_call):
        understanding = {dim: "" for dim in ("project_type", "user", "site", "goal", "constraint", "design_intent")}
        understanding["project_type"] = "乡村民宿"

        question = ask_next_question(
            "乡村民宿", ["乡村民宿"], understanding, asked_questions=["主要给谁使用？"]
        )

        self.assertEqual("住客通常会停留多久？", question["question"])

    @patch(
        "design_discussion._call_llm",
        return_value={
            "fact_updates": {
                "user": {"value": "亲子家庭", "evidence": "主要给亲子家庭住", "status": "clear"},
                "site": {"value": "村口旧粮仓", "evidence": "场地是村口旧粮仓", "status": "clear"},
            },
            "understanding_percent": 48,
            "is_sufficient": False,
            "open_questions": ["旧粮仓哪些结构必须保留？"],
        },
    )
    def test_one_free_answer_can_update_multiple_supported_facts(self, _mock_call):
        answer = "主要给亲子家庭住，场地是村口旧粮仓"
        result = assess_understanding("乡村民宿", ["乡村民宿", answer], known_facts={"project_type": "乡村民宿"})

        self.assertEqual("亲子家庭", result["user"])
        self.assertEqual("村口旧粮仓", result["site"])
        self.assertEqual(48, result["understanding_percent"])

    @patch(
        "design_discussion._call_llm",
        return_value={
            "fact_updates": {
                "site": {"value": "山地", "evidence": "山地", "status": "clear"},
            },
            "understanding_percent": 40,
            "is_sufficient": False,
        },
    )
    def test_unsupported_model_fact_is_not_added_to_the_board(self, _mock_call):
        result = assess_understanding(
            "乡村民宿", ["乡村民宿", "这个我还没想好"], known_facts={"project_type": "乡村民宿"}
        )

        self.assertEqual("", result["site"])

    @patch(
        "design_discussion._call_llm",
        return_value={"fact_updates": {}, "understanding_percent": 35, "is_sufficient": False},
    )
    def test_ai_understanding_percent_cannot_move_backwards(self, _mock_call):
        result = assess_understanding(
            "乡村民宿", ["乡村民宿", "暂时没补充"],
            known_facts={"project_type": "乡村民宿"}, previous_percent=58,
        )

        self.assertEqual(58, result["understanding_percent"])

    @patch("design_discussion._call_llm", return_value={})
    def test_sufficient_understanding_can_stop_without_filling_every_fixed_dimension(self, _mock_call):
        understanding = {
            "project_type": "乡村民宿",
            "user": "亲子家庭",
            "site": "村口旧粮仓",
            "goal": "体验乡村日常",
            "constraint": "",
            "design_intent": "亲近自然",
            "is_sufficient": True,
        }

        question = ask_next_question("乡村民宿", [], understanding)

        self.assertFalse(question["need_more"])

    @patch(
        "design_discussion._call_llm",
        return_value={
            "fact_updates": {
                "project_type": {"value": "乡村民宿改造", "evidence": "乡村民宿", "status": "clear"},
                "user": {"value": "亲子家庭", "evidence": "亲子家庭", "status": "clear"},
                "site": {"value": "村口旧粮仓", "evidence": "村口旧粮仓", "status": "clear"},
                "goal": {"value": "亲近自然", "evidence": "亲近自然", "status": "clear"},
                "constraint": {"value": "保留旧木架", "evidence": "保留旧木架", "status": "clear"},
            },
            "understanding_percent": 65,
            "is_sufficient": False,
            "open_questions": ["木架跨度是多少？", "客房集中还是分散？"],
        },
    )
    def test_non_blocking_design_details_do_not_prevent_readiness(self, _mock_call):
        brief = "乡村民宿，给亲子家庭住，场地是村口旧粮仓，希望亲近自然并保留旧木架"
        result = assess_understanding(brief, [brief])

        self.assertTrue(result["is_sufficient"])
        self.assertGreaterEqual(result["understanding_percent"], 80)


if __name__ == "__main__":
    unittest.main()
