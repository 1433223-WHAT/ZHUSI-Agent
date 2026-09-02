"""Intent Router V1.1 单元测试：分类 Schema、路由决策、降级行为。"""
import unittest
from unittest.mock import Mock, patch

from intent_router import (
    _clarify_target,
    _extract_json,
    _sanitize,
    classify,
    default_classification,
    route,
    state_summary,
)
from conversation_state import empty_state


class SchemaSanitizeTests(unittest.TestCase):
    def test_sanitize_filters_unknown_enum_values(self):
        raw = {
            "intent": "not_a_real_intent",
            "design_stage": "unknown_stage",
            "info_status": "bogus",
            "decision_status": "weird",
            "needs": ["clarify", "bad_value"],
            "reason": "test",
        }
        clean = _sanitize(raw)
        self.assertEqual("design_development", clean["intent"])  # 默认值
        self.assertEqual("undecided", clean["design_stage"])
        self.assertEqual("sufficient", clean["info_status"])
        self.assertEqual("exploring", clean["decision_status"])
        self.assertEqual(["clarify"], clean["needs"])  # 非法值被过滤

    def test_sanitize_accepts_valid_values(self):
        raw = {
            "intent": "design_review", "design_stage": "concept",
            "info_status": "needs_verification", "decision_status": "decided",
            "needs": ["method_search"], "reason": "r",
        }
        clean = _sanitize(raw)
        self.assertEqual("design_review", clean["intent"])
        self.assertEqual("needs_verification", clean["info_status"])
        self.assertEqual("decided", clean["decision_status"])

    def test_needs_as_string_is_normalized(self):
        clean = _sanitize({"needs": "clarify"})
        self.assertEqual(["clarify"], clean["needs"])

    def test_extract_json_handles_code_blocks(self):
        self.assertEqual({"a": 1}, _extract_json('```json\n{"a": 1}\n```'))
        self.assertEqual({"a": 1}, _extract_json('前文 {"a": 1} 后文'))
        self.assertEqual({}, _extract_json("no json here"))


class RouteDecisionTests(unittest.TestCase):
    def test_fuzzy_review_with_missing_info_routes_to_clarify(self):
        cls = {
            "intent": "design_review", "design_stage": "concept",
            "info_status": "insufficient", "decision_status": "exploring",
            "needs": ["clarify"], "reason": "模糊评价",
        }
        result = route("空间有点平", None, cls)
        self.assertEqual("clarify", result["pre_action"])
        self.assertTrue(result["pre_question"])
        self.assertIn("平", result["pre_question"])
        self.assertIn("clarify", result["classification"]["needs"])

    def test_concrete_verification_question_routes_to_method_check(self):
        cls = {
            "intent": "design_review", "design_stage": "development",
            "info_status": "needs_verification", "decision_status": "considering",
            "needs": ["none"], "reason": "已有判断需验证",
        }
        result = route("我的中心大厅会不会导致流线混乱？", None, cls)
        self.assertEqual("method_check", result["pre_action"])
        self.assertIn("画", result["pre_question"])  # 验证动作不是问资料
        self.assertNotIn("提供", result["pre_question"])

    def test_vision_need_routes_to_request_vision(self):
        cls = {
            "intent": "design_review", "design_stage": "review",
            "info_status": "sufficient", "decision_status": "exploring",
            "needs": ["vision"], "reason": "需要看图",
        }
        result = route("帮我看看这张图", None, cls)
        self.assertEqual("request_vision", result["pre_action"])

    def test_verbal_help_me_review_without_visual_reference_stays_direct(self):
        cls = {
            "intent": "design_review", "design_stage": "development",
            "info_status": "insufficient", "decision_status": "considering",
            "needs": ["vision"], "reason": "模型把看看误判为看图",
        }

        result = route(
            "你先帮我看看两种骨架各自最容易出什么问题，别问我选哪个。",
            empty_state(),
            cls,
        )

        self.assertEqual("direct", result["pre_action"])
        self.assertEqual("", result["pre_question"])

    def test_existing_candidate_continuation_does_not_request_vision(self):
        cls = {
            "intent": "design_development", "design_stage": "development",
            "info_status": "insufficient", "decision_status": "considering",
            "needs": ["vision"], "reason": "模型误判为需要图纸",
        }
        state = empty_state()
        state["issue_register"] = {
            "issue-1-1": {
                "text": "中央中庭作为公共空间组织候选",
                "origin": "ai",
                "status": "candidate",
            }
        }

        result = route("基于刚才的中庭方向继续深化入口和首层流线。", state, cls)

        self.assertEqual("direct", result["pre_action"])

    def test_explicit_drawing_followup_still_requests_vision(self):
        cls = {
            "intent": "design_development", "design_stage": "development",
            "info_status": "insufficient", "decision_status": "considering",
            "needs": ["vision"], "reason": "需要读取图纸",
        }
        state = empty_state()
        state["issue_register"] = {
            "issue-1-1": {
                "text": "中央中庭作为公共空间组织候选",
                "origin": "ai",
                "status": "candidate",
            }
        }

        result = route("基于刚才方向继续深化这张平面图。", state, cls)

        self.assertEqual("request_vision", result["pre_action"])

    def test_verbal_rejection_after_sketch_does_not_require_upload(self):
        cls = {
            "intent": "design_review", "design_stage": "development",
            "info_status": "insufficient", "decision_status": "considering",
            "needs": ["vision"], "reason": "模型误判为需要读取图纸",
        }

        result = route(
            "我大概画了一下，感觉两边都是玻璃会很压迫。我不想继续 A 了，能不能换个角度看？",
            empty_state(),
            cls,
        )

        self.assertEqual("direct", result["pre_action"])
        self.assertEqual("", result["pre_question"])

    def test_explicit_no_image_verbal_request_does_not_require_upload(self):
        cls = {
            "intent": "design_development", "design_stage": "development",
            "info_status": "insufficient", "decision_status": "considering",
            "needs": ["vision"], "reason": "模型误判为需要读取图纸",
        }

        result = route(
            "我现在没有图可以上传，只是口头说我的感受。请直接换一个角度继续帮我想。",
            empty_state(),
            cls,
        )

        self.assertEqual("direct", result["pre_action"])
        self.assertEqual("", result["pre_question"])

    def test_verbal_route_rejection_with_vague_evaluation_stays_direct(self):
        cls = {
            "intent": "design_review", "design_stage": "development",
            "info_status": "insufficient", "decision_status": "considering",
            "needs": ["clarify"], "reason": "模型只看见模糊评价",
        }

        messages = (
            "我没画草图，但这套上下分层的组织太常规了，先停止这个方案，从整体关系重新探索。",
            "目前没有上传图纸。我不采用这套空间分法，请收起当前路线，再给我整体层面的可能性。",
        )
        for message in messages:
            with self.subTest(message=message):
                result = route(message, empty_state(), cls)
                self.assertEqual("direct", result["pre_action"])
                self.assertEqual("", result["pre_question"])

    def test_decided_development_routes_to_direct(self):
        cls = {
            "intent": "design_development", "design_stage": "development",
            "info_status": "sufficient", "decision_status": "decided",
            "needs": ["none"], "reason": "已拍板",
        }
        result = route("我决定中心大厅，帮我深化", None, cls)
        self.assertEqual("direct", result["pre_action"])

    def test_knowledge_query_routes_to_direct_with_retrieval(self):
        cls = {
            "intent": "knowledge_query", "design_stage": "undecided",
            "info_status": "sufficient", "decision_status": "exploring",
            "needs": ["case_search"], "reason": "知识查询",
        }
        result = route("光之教堂为什么狭缝采光", None, cls)
        self.assertEqual("direct", result["pre_action"])
        self.assertIn("case_search", result["retrieval_targets"])

    def test_default_classification_routes_to_direct(self):
        result = route("任意消息", None, None)
        self.assertEqual("direct", result["pre_action"])
        self.assertEqual("exploring", result["classification"]["decision_status"])

    def test_conflicting_info_routes_to_direct(self):
        cls = {
            "intent": "design_development", "design_stage": "development",
            "info_status": "conflicting", "decision_status": "considering",
            "needs": ["none"], "reason": "冲突",
        }
        result = route("你说过入口放东侧，现在又说放西侧？", None, cls)
        self.assertEqual("direct", result["pre_action"])


class ClarifyTargetTests(unittest.TestCase):
    def test_target_inference(self):
        self.assertEqual("功能组织", _clarify_target("空间有点平，流线也不太顺"))
        self.assertEqual("视觉表达", _clarify_target("立面太平淡"))
        self.assertEqual("场地关系", _clarify_target("入口处有点问题"))
        self.assertEqual("空间体验", _clarify_target("感觉有点压抑"))


class ClassifyFallbackTests(unittest.TestCase):
    @patch("intent_router.requests.post")
    def test_classify_success_returns_sanitized(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"choices": [{"message": {"content": '{"intent": "design_review", "design_stage": "concept", "info_status": "insufficient", "decision_status": "exploring", "needs": ["clarify"], "reason": "模糊"}'}}]}
        mock_post.return_value = response

        result = classify("空间有点平")
        self.assertIsNotNone(result)
        self.assertEqual("design_review", result["intent"])
        self.assertEqual("insufficient", result["info_status"])

    @patch("intent_router.requests.post", side_effect=RuntimeError("network down"))
    def test_classify_failure_returns_none(self, _mock_post):
        self.assertIsNone(classify("空间有点平"))  # 静默降级，不抛异常

    def test_state_summary_extracts_confirmed(self):
        state = empty_state()
        state["project"]["project_type"] = {"value": "社区图书馆", "status": "confirmed", "source": "student"}
        state["project"]["scale"] = {"value": "2500平方米", "status": "confirmed", "source": "student"}
        summary = state_summary(state)
        self.assertIn("社区图书馆", summary)
        self.assertIn("2500平方米", summary)

    def test_state_summary_empty(self):
        self.assertEqual("（暂无已确认事实）", state_summary(empty_state()))


if __name__ == "__main__":
    unittest.main()
