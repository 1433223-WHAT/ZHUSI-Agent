import unittest
from unittest.mock import Mock, patch

from design_critic import critique, revise_with_diff
from design_discussion import _explicit_fact_updates, apply_fact_updates, assess_understanding
from direction_proposer import _filter_relevant_knowledge, _unverified_direction_note, _verified_evidence


class UnderstandingCorrectionTests(unittest.TestCase):
    @patch("design_discussion._call_llm")
    def test_option_answer_is_bound_to_the_question_dimension(self, mock_llm):
        mock_llm.return_value = {
            "fact_updates": {
                "project_type": {
                    "value": "面向大众的公共博物馆",
                    "evidence": "面向大众的公共博物馆",
                    "status": "clear",
                    "action": "set",
                }
            }
        }

        result = assess_understanding(
            "博物馆",
            ["博物馆", "面向大众的公共博物馆"],
            {"project_type": "博物馆"},
            answer_dimension="user",
        )

        self.assertEqual("博物馆", result["project_type"])
        self.assertEqual("面向大众的公共博物馆", result["user"])
        self.assertEqual([], result["conflicts"])

    @patch("design_discussion._call_llm", return_value={})
    def test_short_building_type_creates_project_type_conflict(self, _mock_llm):
        result = assess_understanding(
            "博物馆",
            ["博物馆", "写字楼"],
            {"project_type": "博物馆", "user": "面向大众的公共博物馆"},
        )

        self.assertEqual("project_type", result["conflicts"][0]["dim"])
        self.assertEqual("写字楼", result["conflicts"][0]["candidate"])

    def test_explicit_site_phrase_is_available_when_model_omits_update(self):
        updates = _explicit_fact_updates("另外场地在河边空地")

        self.assertEqual("河边空地", updates["site"]["value"])
        self.assertEqual("set", updates["site"]["action"])

    def test_explicit_correction_replaces_old_fact(self):
        result = apply_fact_updates(
            {"user": "亲子家庭"},
            {"user": {"value": "亲子家庭", "status": "clear"}},
            {"user": {"value": "独居艺术家", "evidence": "不是亲子家庭，是独居艺术家", "status": "clear", "action": "replace"}},
            "刚才说错了，不是亲子家庭，是独居艺术家",
        )

        self.assertEqual("独居艺术家", result["facts"]["user"])
        self.assertEqual("corrected", result["changes"][0]["type"])
        self.assertFalse(result["conflicts"])

    def test_unresolved_conflict_does_not_overwrite_confirmed_fact(self):
        result = apply_fact_updates(
            {"site": "村口旧粮仓"},
            {"site": {"value": "村口旧粮仓", "status": "clear"}},
            {"site": {"value": "河边空地", "evidence": "场地在河边空地", "status": "clear", "action": "set"}},
            "另外场地在河边空地",
        )

        self.assertEqual("村口旧粮仓", result["facts"]["site"])
        self.assertEqual("conflict", result["states"]["site"]["status"])
        self.assertEqual("河边空地", result["conflicts"][0]["candidate"])

    def test_explicit_retraction_removes_fact(self):
        result = apply_fact_updates(
            {"constraint": "必须保留旧木架"},
            {"constraint": {"value": "必须保留旧木架", "status": "clear"}},
            {"constraint": {"value": "", "evidence": "取消保留旧木架", "status": "unknown", "action": "retract"}},
            "取消保留旧木架这个要求",
        )

        self.assertNotIn("constraint", result["facts"])
        self.assertEqual("retracted", result["changes"][0]["type"])


class KnowledgeFitTests(unittest.TestCase):
    def test_unverified_direction_uses_required_disclosure(self):
        note = _unverified_direction_note()
        self.assertIn("该建议未找到合适的本地知识库依据，需要后续核实。", note["message"])

    def test_irrelevant_knowledge_is_filtered_instead_of_forced(self):
        cases, theories, methods = _filter_relevant_knowledge(
            [{"name": "无关案例", "score": 0.29}],
            [{"name": "无关理论", "score": 0.24}],
            [{"name": "无关方法", "score": 0.25}],
        )

        self.assertEqual([], cases)
        self.assertEqual([], theories)
        self.assertEqual([], methods)

    def test_verified_evidence_contains_fit_and_transfer_boundary(self):
        direction = {
            "name": "院落生活型",
            "evidence": {
                "case": {
                    "name": "住吉的长屋",
                    "why": "借鉴院落组织日常生活",
                    "fit": {
                        "project_type": 78,
                        "scale": 82,
                        "function": 76,
                        "site_climate": 55,
                        "transferable": "院落连接室内外生活",
                        "not_copy": "不能照搬封闭临街界面",
                        "risk": "寒冷地区需调整露天交通",
                    },
                },
                "theory": {"name": "场所精神", "why": "回应村庄环境"},
                "method": {"name": "框景借景", "why": "引入田野视线"},
            },
        }
        cases = [{"name": "住吉的长屋", "strategy": "内向院落", "content": "以中庭组织住宅日常。"}]
        theories = [{"name": "场所精神", "content": "回应场地特征。"}]
        methods = [{"name": "框景借景", "content": "以开口控制视域。"}]

        result = _verified_evidence(direction, cases, theories, methods)
        fit = result["evidence"]["case"]["fit"]

        self.assertEqual(78, fit["project_type"])
        self.assertTrue(fit["transferable"])
        self.assertTrue(fit["not_copy"])
        self.assertIn(result["evidence_status"], {"verified", "partial"})


class VersionAndCriticTests(unittest.TestCase):
    @patch("design_critic.requests.post")
    def test_feedback_version_inherits_evidence_and_records_changes(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": '{"revised_plan":"# V2 完整方案","diff_summary":{"feedback_response":"入口更开放","changes":[],"kept":["院落"],"removed":["封闭门厅"]},"evidence_changes":{"kept":["住吉的长屋"],"added":[],"invalidated":[]}}'}}]
        }
        mock_post.return_value = response
        evidence = {"case": {"name": "住吉的长屋"}}

        result = revise_with_diff(
            "乡村民宿", "# V1", "入口更开放", {},
            version_number=2, selected_direction={"name": "院落生活型", "evidence": evidence},
        )

        self.assertEqual(2, result["version"]["number"])
        self.assertEqual("院落生活型", result["version"]["direction"])
        self.assertEqual(evidence, result["version"]["knowledge_evidence"])
        self.assertEqual(["院落"], result["version"]["kept"])

    @patch("design_critic.requests.post")
    def test_critic_returns_eight_evidence_based_criteria(self, mock_post):
        criteria = {
            key: {"score": 75, "status": "部分解决", "evidence": "方案原文", "comment": "需深化"}
            for key in (
                "requirement_response", "site_response", "function_flow", "spatial_experience",
                "architectural_scale", "constructability", "knowledge_transfer", "student_intent",
            )
        }
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"choices": [{"message": {"content": __import__("json").dumps({"score": 75, "criteria": criteria})}}]}
        mock_post.return_value = response

        result = critique("乡村民宿", "方案原文")

        self.assertEqual(8, len(result["criteria"]))
        self.assertTrue(all(item["evidence"] for item in result["criteria"].values()))


if __name__ == "__main__":
    unittest.main()
