import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _experience_patch_sanitized_replay as replay


class ExperiencePatchSanitizedReplayTests(unittest.TestCase):
    def test_unconditioned_site_inference_counts_as_strong(self):
        text = "南侧边界开敞，可承接公共活动，适合放入口。"
        patterns = [r"南侧边界开敞.{0,35}(?:适合|可承接).{0,20}(?:入口|公共)"]

        self.assertEqual(patterns, replay._strong_hits(text, patterns))

    def test_candidate_site_inference_does_not_count_as_strong(self):
        text = "南侧边界开敞，可以把入口作为候选，需结合主要到达方向验证。"
        patterns = [r"南侧边界开敞.{0,35}(?:入口|公共)"]

        self.assertEqual([], replay._strong_hits(text, patterns))


if __name__ == "__main__":
    unittest.main()
