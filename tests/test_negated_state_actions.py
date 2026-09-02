import unittest
from copy import deepcopy
from unittest.mock import patch

from architect_chat import _apply_state_revision, chat_turn, classify_intent
from conversation_state import empty_state, update_state


SUMMARY_REQUEST = (
    "不是修改或撤销任何决定，也不是要建立版本。"
    "我是在要求你输出当前方案总结。"
    "请直接给出两层空间骨架、主要流线、体量和剖面动作，不要提问。"
)


def _state_with_confirmed_scheme() -> dict:
    state = empty_state()
    state["student_decisions"] = [{
        "value": "采用中央中庭组织，北侧入口作为当前方案入口",
        "status": "confirmed",
        "source": "student",
        "turn_id": 12,
    }]
    state["issue_register"] = {
        "flow": {
            "text": "主要流线组织",
            "status": "active",
            "source": "student",
            "turn_id": 12,
        }
    }
    return state


class NegatedStateActionTests(unittest.TestCase):
    def test_common_function_names_are_kept_in_project_state(self):
        message = "功能有活动室、阅览、小剧场和办公室。"

        updated = update_state(empty_state(), message, turn_id=2)

        value = updated["project"]["functions"]["value"]
        self.assertIn("活动室", value)
        self.assertIn("阅览", value)
        self.assertIn("小剧场", value)
        self.assertIn("办公室", value)

    def test_rejecting_hall_route_does_not_clear_confirmed_functions(self):
        state = update_state(
            empty_state(),
            "功能有活动室、阅览、小剧场和办公室。",
            turn_id=2,
        )
        original = deepcopy(state["project"]["functions"])

        updated = update_state(
            state,
            "我不想用大厅当心脏，功能先还按这几个，直接改一版。",
            turn_id=4,
        )

        self.assertEqual(original, updated["project"]["functions"])
        self.assertEqual("", updated.get("pending_clarification"))
        self.assertFalse(any(
            item.get("dimension") == "functions" and item.get("type") == "retracted"
            for item in updated["change_log"]
        ))

    def test_negated_retraction_is_not_classified_as_retract(self):
        self.assertNotEqual("retract_fact", classify_intent(SUMMARY_REQUEST))

    def test_negated_retraction_preserves_confirmed_decision(self):
        state = _state_with_confirmed_scheme()

        updated = update_state(state, SUMMARY_REQUEST, turn_id=18)

        self.assertEqual(state["student_decisions"], updated["student_decisions"])
        self.assertFalse(any(item.get("type") == "retracted" for item in updated["change_log"]))

    def test_response_format_instruction_does_not_reject_flow_issue(self):
        state = _state_with_confirmed_scheme()
        before = deepcopy(state)

        opener = _apply_state_revision(state, SUMMARY_REQUEST, turn_id=18)

        self.assertEqual("", opener)
        self.assertEqual(before["issue_register"], state["issue_register"])
        self.assertEqual(before.get("rejected_assumptions"), state.get("rejected_assumptions"))

    def test_output_wording_constraint_does_not_reject_engineering_issue(self):
        state = empty_state()
        message = "舞蹈教室放二层会不会有问题？但别说只能放一层。"

        opener = _apply_state_revision(state, message, turn_id=2)

        self.assertEqual("", opener)
        self.assertEqual([], state.get("rejected_assumptions"))

    def test_real_retraction_still_removes_confirmed_decision(self):
        state = _state_with_confirmed_scheme()

        updated = update_state(state, "撤销刚才的中庭决定。", turn_id=18)

        self.assertEqual([], updated["student_decisions"])
        self.assertEqual("retracted", updated["change_log"][-1]["type"])

    def test_rejecting_unconfirmed_candidate_does_not_remove_confirmed_entry_decision(self):
        state = _state_with_confirmed_scheme()

        updated = update_state(
            state,
            "我不想要双入口这个候选了，只收回这个候选，继续讨论单入口。",
            turn_id=18,
        )

        self.assertEqual(state["student_decisions"], updated["student_decisions"])
        self.assertFalse(any(item.get("type") == "retracted" for item in updated["change_log"]))
        self.assertEqual("", updated.get("pending_clarification"))

    def test_rejecting_ai_route_with_project_facts_does_not_ask_which_decision_to_revoke(self):
        state = empty_state()
        state["project"]["project_type"] = {
            "value": "社区文化中心", "status": "confirmed", "source": "student"
        }
        state["project"]["site"] = {
            "value": "北侧道路、东侧公园", "status": "confirmed", "source": "student"
        }
        state["issue_register"] = {
            "ai-route": {
                "text": "底层公共客厅、楼上安静房间",
                "origin": "ai",
                "status": "candidate",
            }
        }

        for message in (
            "停止当前这套空间组织，退回整体关系重新探索。",
            "把当前空间路线收回来，回到整体重新推。",
            "把这个方案收起来，我没有确认它，也不是要撤销项目事实。",
        ):
            with self.subTest(message=message):
                updated = update_state(state, message, turn_id=5)
                self.assertEqual([], updated["student_decisions"])
                self.assertEqual("", updated.get("pending_clarification"))
                self.assertEqual(
                    "社区文化中心",
                    updated["project"]["project_type"]["value"],
                )

    def test_explicit_route_rejection_does_not_depend_on_ai_issue_registration(self):
        state = empty_state()
        state["project"]["project_type"] = {
            "value": "社区中心", "status": "confirmed", "source": "student"
        }
        state["project"]["site"] = {
            "value": "北侧社区路、东侧绿地", "status": "confirmed", "source": "student"
        }

        updated = update_state(
            state,
            "我不想继续环院，也不要刚才那条线性轴。这两个方向都收回，回到整个建筑。",
            turn_id=5,
        )

        self.assertEqual("", updated.get("pending_clarification"))
        self.assertEqual("社区中心", updated["project"]["project_type"]["value"])
        self.assertEqual("北侧社区路、东侧绿地", updated["project"]["site"]["value"])

    @patch("architect_chat.router_classify", return_value=None)
    @patch("architect_chat._call_deepseek", return_value="下面直接整理当前方案的两层空间骨架、主要流线、体量和剖面动作。")
    def test_full_turn_keeps_decision_and_returns_requested_summary(self, _mock_model, _mock_router):
        state = _state_with_confirmed_scheme()

        result = chat_turn(SUMMARY_REQUEST, [], state, turn_id=18)

        self.assertEqual(state["student_decisions"], result["state"]["student_decisions"])
        self.assertEqual("active", result["state"]["issue_register"]["flow"]["status"])
        self.assertNotIn("先放下", result["reply"])
        self.assertIn("两层空间骨架", result["reply"])


if __name__ == "__main__":
    unittest.main()
