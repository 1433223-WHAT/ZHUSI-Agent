import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _candidate_confirmation_protocol_live_validation as validation


class CandidateConfirmationProtocolValidationTests(unittest.TestCase):
    def test_comparing_rejected_route_is_not_recurrence(self):
        text = (
            "中庭这个方向先放一边。两种逻辑的差别是："
            "中庭是中心吸附，线性街道是路径串联。"
        )

        self.assertFalse(validation._old_route_recurrence(text))

    def test_continuing_rejected_route_is_recurrence(self):
        text = "中庭继续作为当前空间骨架的组织核心。"

        self.assertTrue(validation._old_route_recurrence(text))


if __name__ == "__main__":
    unittest.main()
