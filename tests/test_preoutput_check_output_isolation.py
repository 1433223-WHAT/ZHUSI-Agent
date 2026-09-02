import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import architect_chat as ac


class PreoutputCheckOutputIsolationTests(unittest.TestCase):
    def _run_hidden_check(
        self,
        model_output: str,
        draft: str = "原始设计草案",
        last_user: str = "",
        state: dict | None = None,
    ) -> str:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": model_output}}]
        }
        old_key = ac.DEEPSEEK_API_KEY
        try:
            ac.DEEPSEEK_API_KEY = "test-key"
            with patch("architect_chat.requests.post", return_value=response):
                return ac._hidden_check_revise(draft, state or {}, "test policy", last_user)
        finally:
            ac.DEEPSEEK_API_KEY = old_key

    def test_keeps_only_final_answer_when_check_trace_precedes_it(self):
        leaked = """好，我先检查上一版草案。

**内部检查结果：**
- 证据问题：需要降级。
- 一致性问题：没有发现。

**修订后完整方案：**

---

这是修订后的学生可见设计方案。"""

        result = self._run_hidden_check(leaked)

        self.assertEqual("这是修订后的学生可见设计方案。", result)

    def test_falls_back_to_draft_when_only_check_trace_is_returned(self):
        leaked_only = """**内部检查结果：**
- 证据问题：需要降级。
- 一致性问题：没有发现。"""

        result = self._run_hidden_check(leaked_only)

        self.assertEqual("原始设计草案", result)

    def test_keeps_answer_after_observed_parenthetical_marker(self):
        leaked = """我按照你设定的规则进行了内部检查。检查结果如下：

一、证据核查：没有问题。

以下为修订后的完整方案（与原方案一致）：

---

这是学生最终应看到的设计回答。"""

        result = self._run_hidden_check(leaked)

        self.assertEqual("这是学生最终应看到的设计回答。", result)

    def test_falls_back_when_observed_check_trace_has_no_final_answer(self):
        leaked_only = """我按照你设定的规则进行了内部检查。检查结果如下：

一、证据核查：没有问题。
二、一致性核查：没有问题。"""

        result = self._run_hidden_check(leaked_only)

        self.assertEqual("原始设计草案", result)

    def test_keeps_answer_after_sentence_style_final_marker(self):
        leaked = """好，我重新检查了一遍刚才那版草案，发现三处需要修正的地方。现在输出修订后的完整方案。

---

这是修订后的空间骨架。"""

        result = self._run_hidden_check(leaked)

        self.assertEqual("这是修订后的空间骨架。", result)

    def test_falls_back_for_sentence_style_check_trace_without_answer(self):
        leaked_only = "好，我重新检查了一遍刚才那版草案，发现三处需要修正的地方。"

        result = self._run_hidden_check(leaked_only)

        self.assertEqual("原始设计草案", result)

    def test_preserves_normal_revised_answer(self):
        revised = "这是正常修订后的完整设计回答。"

        result = self._run_hidden_check(revised)

        self.assertEqual(revised, result)

    def test_keeps_answer_after_markdown_heading_without_colon(self):
        leaked = """**修订后的完整方案**

---

这是学生最终应看到的设计回答。"""

        result = self._run_hidden_check(leaked)

        self.assertEqual("这是学生最终应看到的设计回答。", result)

    def test_confirmed_user_decision_rejects_hidden_check_demotion(self):
        demoted = """**修订后的完整方案**

---

这只是暂定起点，非你的决定，中央中庭尚未确认。"""

        result = self._run_hidden_check(
            demoted,
            draft="中央中庭作为组织母题已经确认，下面深化入口和流线。",
            last_user="我已经决定采用中央中庭组织方式，请继续深化。",
        )

        self.assertEqual("中央中庭作为组织母题已经确认，下面深化入口和流线。", result)

    def test_natural_language_confirmation_rejects_hidden_check_demotion(self):
        demoted = "这个方向仍是候选，尚未确认采用。"
        draft = "中央中庭已经作为当前方案前提，下面深化入口、流线和剖面。"

        result = self._run_hidden_check(
            demoted,
            draft=draft,
            last_user="那就按这个做，继续深化。",
        )

        self.assertEqual(draft, result)

    def test_previous_confirmed_decision_rejects_later_hidden_check_demotion(self):
        draft = "继续深化已确认的中央中庭方案，下面展开入口和剖面。"
        state = {
            "student_decisions": [
                {"value": "中央中庭方案定了", "turn_id": 2, "source": "student"}
            ]
        }

        result = self._run_hidden_check(
            "这仍是待发展的设计意图，只是候选，不是定案。",
            draft=draft,
            last_user="继续深化首层和二层关系。",
            state=state,
        )

        self.assertEqual(draft, result)

    def test_hidden_check_receives_current_user_message(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": "正常修订回答"}}]
        }
        old_key = ac.DEEPSEEK_API_KEY
        try:
            ac.DEEPSEEK_API_KEY = "test-key"
            with patch("architect_chat.requests.post", return_value=response) as post_mock:
                ac._hidden_check_revise(
                    "原始设计草案",
                    {},
                    "test policy",
                    "我已经决定采用中央中庭。",
                )
            payload = post_mock.call_args.kwargs["json"]
            system_content = payload["messages"][0]["content"]
            self.assertIn("【当前用户输入】", system_content)
            self.assertIn("我已经决定采用中央中庭。", system_content)
        finally:
            ac.DEEPSEEK_API_KEY = old_key


if __name__ == "__main__":
    unittest.main()
