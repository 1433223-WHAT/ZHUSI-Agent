"""V1.0 证据分层泛化回归测试。

验证 V1.0 后证据边界不再依赖"北侧/南侧""四栏"等具体测试题经验，
而是适用于任意方向、任意建筑类型、任意设计阶段。

判定标准：错误类型从"编造事实 / 替学生决定"下降到"条件化不足 / 验证点不足"。
"""
import unittest
from unittest.mock import Mock, patch

from architect_chat import _needs_boundary_check
from collaboration_focus import empty_focus, response_policy, update_focus
from conversation_state import empty_state


class EvidenceLayerGeneralizationTests(unittest.TestCase):
    """测试 1：方向泛化——换方向（东/西）后边界规则同样生效，不依赖北/南词表。"""

    def test_direction_generalization_policy_has_no_direction_names(self):
        state = update_focus(empty_state(), "场地东侧是主路，西侧是宿舍区，请帮我分析入口。", 1)
        policy = response_policy(state)
        # 通用规则中不得出现具体方向名或四栏字样
        for forbidden in ("北侧", "南侧", "四栏", "逐栏"):
            self.assertNotIn(forbidden, policy)
        # 必须包含方向-角色绑定禁令与条件化要求
        self.assertIn("不把方向与价值角色绑定", policy)
        self.assertIn("可检验的判断路径", policy)

    def test_needs_boundary_check_fires_for_any_direction_question(self):
        # 换方向后高风险触发依然生效
        self.assertTrue(_needs_boundary_check("主入口放东侧还是西侧？", "project_brief", ""))
        self.assertTrue(_needs_boundary_check("", "project_brief", "东侧更适合作为主入口。"))
        self.assertFalse(_needs_boundary_check("光之教堂建于哪年？", "analyze_case", ""))

    def test_direction_role_binding_terms_are_not_hardcoded(self):
        # V1.0：不硬编码任何具体方向词；通用规则里只有"方向"这个抽象词
        state = update_focus(empty_state(), "帮我分析入口方向。", 1)
        policy = response_policy(state)
        self.assertIn("方向", policy)
        for direction in ("东侧", "西侧", "南侧", "北侧"):
            self.assertNotIn(direction, policy)


class TypeExperienceGeneralizationTests(unittest.TestCase):
    """测试 2：类型经验——功能类型经验必须条件化，不能写成定论。"""

    def test_type_experience_rule_in_policy(self):
        state = update_focus(empty_state(), "我想做儿童活动中心，里面有阅读、手工、游戏和小剧场。", 1)
        policy = response_policy(state)
        self.assertIn("类型经验", policy)
        self.assertIn("成立条件和待验证因素", policy)

    def test_type_experience_rewrite_direction(self):
        # 断言：Boundary Checker 指令要求把类型经验改成条件式
        state = update_focus(empty_state(), "儿童活动中心需要高差吗？", 1)
        policy = response_policy(state)
        # 通用规则覆盖"类型经验写成定论"的改写要求
        self.assertIn("可检验的判断路径", policy)


class DesignStampGeneralizationTests(unittest.TestCase):
    """测试 3：设计经验盖章——"这个方向是对的"类表达必须改为可发展方向。"""

    def test_stamp_terms_covered_by_high_risk_checker(self):
        # 输出含"是对的""很需要"等盖章词时，必须触发边界改写
        self.assertTrue(_needs_boundary_check("", "general_architecture_chat", "这个方向是对的，很多项目都这么做。"))
        self.assertTrue(_needs_boundary_check("", "general_architecture_chat", "社区中心很需要这种公共氛围。"))
        self.assertFalse(_needs_boundary_check("", "general_architecture_chat", "我们可以先画一张功能关系图。"))

    def test_policy_requires_conditional_path_instead_of_stamp(self):
        state = update_focus(empty_state(), "你觉得我楼梯放一侧的做法对吗？", 1)
        policy = response_policy(state)
        self.assertIn("可检验的判断路径", policy)
        self.assertIn("不把方向与价值角色绑定", policy)


class DecisionDeepeningGeneralizationTests(unittest.TestCase):
    """测试 4：拍板深化——学生拍板后沿决定深化，不反复比较未选方向。"""

    def test_student_decision_is_not_questioned_again(self):
        # 学生拍板"中心共享大厅"后，policy 不应再要求重新比较组织方式
        state = update_focus(empty_state(), "我决定采用中心共享大厅+周边功能房间的组织方式，帮我深化。", 1)
        policy = response_policy(state)
        self.assertIn("学生明确选择后作为当前项目前提继续深化", policy)
        self.assertIn("不再反复质疑", policy)


if __name__ == "__main__":
    unittest.main()
