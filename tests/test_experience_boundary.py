import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import architect_chat as ac


class ExperienceBoundaryTests(unittest.TestCase):
    def test_experience_boundary_is_noop_when_disabled(self):
        old_enabled = ac.ENABLE_EXPERIENCE_BOUNDARY
        try:
            ac.ENABLE_EXPERIENCE_BOUNDARY = False
            policy = ac._apply_experience_boundary_policy(
                "base policy",
                "北侧临城市道路，讨论入口组织。",
                "design_request",
            )
            self.assertEqual(policy, "base policy")
        finally:
            ac.ENABLE_EXPERIENCE_BOUNDARY = old_enabled

    def test_experience_boundary_injects_minimal_generator_guard_when_enabled(self):
        old_enabled = ac.ENABLE_EXPERIENCE_BOUNDARY
        try:
            ac.ENABLE_EXPERIENCE_BOUNDARY = True
            policy = ac._apply_experience_boundary_policy(
                "base policy",
                "北侧临城市道路，南侧有公园，讨论入口和公共空间。",
                "design_request",
            )
            self.assertIn("Experience Boundary", policy)
            self.assertIn("不得把建筑经验直接写成当前项目事实", policy)
            self.assertIn("北侧道路", policy)
            self.assertIn("主入口", policy)
            self.assertIn("如果北侧道路承担主要到达功能", policy)
            self.assertIn("不要检查设计美学", policy)
            self.assertIn("不要改变最终回答格式", policy)
        finally:
            ac.ENABLE_EXPERIENCE_BOUNDARY = old_enabled


if __name__ == "__main__":
    unittest.main()
