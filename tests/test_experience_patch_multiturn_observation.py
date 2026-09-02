import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _experience_patch_multiturn_observation as observation


class ExperiencePatchMultiturnObservationTests(unittest.TestCase):
    def test_retracted_rule_is_not_counted_as_strong_assertion(self):
        text = "你没有确认每班必须设置独立小院，这个前提现在收回。"
        patterns = [r"(?:每班|每个班).{0,24}(?:必须|应该|独立小院)"]

        self.assertEqual([], observation._strong_hits(text, patterns))

    def test_retracted_route_is_not_counted_as_recurrence(self):
        text = "收回主入口放在北侧这个方向，改为比较东西两侧。"
        patterns = [r"(?:主入口|主要入口).{0,12}(?:放|设|位于|安排)(?:在|于)?北侧"]

        self.assertEqual([], observation._rejected_hits(text, patterns))

    def test_unretracted_route_still_counts_as_recurrence(self):
        text = "主入口继续放在北侧，东西两侧只作为次入口。"
        patterns = [r"(?:主入口|主要入口).{0,12}(?:放|设|位于|安排)(?:在|于)?北侧"]

        self.assertEqual(patterns, observation._rejected_hits(text, patterns))

    def test_supervision_cannot_break_is_not_a_bedroom_spatial_rule(self):
        text = "寝室独立了，但老师照看不能断。"
        patterns = observation.CONVERSATIONS[1]["strong_patterns"]

        self.assertEqual([], observation._strong_hits(text, patterns))

    def test_bedroom_must_pass_activity_room_is_still_a_spatial_rule(self):
        text = "寝室必须通过活动室到达室外。"
        patterns = observation.CONVERSATIONS[1]["strong_patterns"]

        self.assertTrue(observation._strong_hits(text, patterns))


if __name__ == "__main__":
    unittest.main()
