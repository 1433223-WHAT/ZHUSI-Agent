import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _implicit_route_guidance_regression_validation as validation


class ImplicitRouteGuidanceValidationTests(unittest.TestCase):
    def test_ai_route_internal_choice_is_counted(self):
        text = "先给一版公共大厅骨架。这个方向更偏集中还是分散？"

        self.assertTrue(validation.implicit_route_hits(text, "我想做得开放一点。"))

    def test_user_route_internal_choice_is_allowed(self):
        text = "先展开公共主街。你希望这条公共主街更偏穿行还是停留？"

        self.assertEqual(
            [],
            validation.implicit_route_hits(text, "我想试试公共主街这个方向。"),
        )

    def test_user_route_can_compare_component_options(self):
        text = (
            "沿公共主街继续深化。"
            "这条公共主街靠外墙获得自然光，还是夹在功能之间并通过天窗或中庭采光？"
        )

        self.assertEqual(
            [],
            validation.implicit_route_hits(text, "我想试试公共主街这个方向。"),
        )

    def test_open_evaluation_of_ai_candidate_is_allowed(self):
        text = "先给一版公共大厅骨架。这个测试骨架是否回应你的开放目标？"

        self.assertEqual(
            [],
            validation.implicit_route_hits(text, "我想做得开放一点。"),
        )

    def test_comparing_evaluation_standards_is_not_route_guidance(self):
        text = (
            "先给一版公共大厅骨架。"
            "你更希望先用什么标准检验上面的测试骨架："
            "它是否回应你的使用目标、空间体验，还是场地条件？"
        )

        self.assertEqual(
            [],
            validation.implicit_route_hits(text, "我想做得开放一点。"),
        )


if __name__ == "__main__":
    unittest.main()
