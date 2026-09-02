import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _candidate_boundary_multiturn_validation as validation


class CandidateBoundaryMultiturnValidationTests(unittest.TestCase):
    def test_non_atrium_route_is_not_counted_as_atrium_recurrence(self):
        text = "我们换一个不依赖中庭的空间骨架，采用线性主廊组织。"

        self.assertEqual([], validation._rejected_route_hits(text, ["中庭"]))

    def test_continued_atrium_route_is_counted_as_recurrence(self):
        text = "中庭继续作为当前空间骨架的组织核心。"

        self.assertTrue(validation._rejected_route_hits(text, ["中庭"]))


if __name__ == "__main__":
    unittest.main()
