import unittest
from unittest.mock import Mock, patch

import design_critic


class RevisionSafetyTests(unittest.TestCase):
    @patch("design_critic.requests.post")
    def test_empty_model_revision_keeps_the_previous_plan_visible(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"choices": [{"message": {"content": "{}"}}]}
        mock_post.return_value = mock_response

        result = design_critic.revise_with_diff("乡村民宿", "# 方案 V1\n原有方案内容", "入口更开放")

        self.assertIn("原有方案内容", result["revised_plan"])
        self.assertIn("未返回完整", result["diff_summary"]["feedback_response"])


if __name__ == "__main__":
    unittest.main()
