"""视觉分析健壮性测试：JSON 解析容错 + Debug 链路。"""
import unittest
from unittest.mock import Mock, patch

from image_analyzer import _extract_json_robust


class RobustJsonExtractTests(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual({"a": 1}, _extract_json_robust('{"a": 1}'))

    def test_markdown_code_block(self):
        self.assertEqual({"a": 1}, _extract_json_robust('```json\n{"a": 1}\n```'))

    def test_text_wrapped_json(self):
        self.assertEqual({"a": 1}, _extract_json_robust('以下是分析结果：{"a": 1} 完毕'))

    def test_leading_text_before_brace(self):
        self.assertEqual({"visible_facts": []}, _extract_json_robust('图片分析：\n{"visible_facts": []}'))

    def test_trailing_comma(self):
        self.assertEqual({"a": 1}, _extract_json_robust('{"a": 1,}'))

    def test_truncated_balanced_brace(self):
        # 模型返回被截断但花括号平衡
        self.assertEqual({"a": 1}, _extract_json_robust('{"a": 1'))

    def test_invalid_returns_none(self):
        self.assertIsNone(_extract_json_robust("完全不是 JSON"))
        self.assertIsNone(_extract_json_robust(""))


class VisionDebugChainTests(unittest.TestCase):
    @patch("image_analyzer.requests.post")
    def test_success_chain_parses_content(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "output": {"choices": [{"message": {"content": '{"image_type":"plan","visible_facts":["有矩形"],"inferences":[],"unknowns":["缺比例尺"],"architecture_questions":[],"warnings":[]}'}}]}
        }
        mock_post.return_value = response
        from image_analyzer import _call_qwen_vl
        result = _call_qwen_vl(b"fakedata", "image/png", "测试")
        self.assertEqual("plan", result["image_type"])
        self.assertEqual(["有矩形"], result["visible_facts"])

    @patch("image_analyzer.requests.post")
    def test_content_list_format(self, mock_post):
        # DashScope 可能返回 content 为 list
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "output": {"choices": [{"message": {"content": [{"text": '{"image_type":"sketch","visible_facts":["X"],"inferences":[],"unknowns":[],"architecture_questions":[],"warnings":[]}'}]}}]}
        }
        mock_post.return_value = response
        from image_analyzer import _call_qwen_vl
        result = _call_qwen_vl(b"fakedata", "image/png", "测试")
        self.assertEqual("sketch", result["image_type"])


if __name__ == "__main__":
    unittest.main()
