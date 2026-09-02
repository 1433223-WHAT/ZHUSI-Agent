import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from architect_chat import _enforce_response_boundaries
from collaboration_focus import empty_focus, GENERAL_EVIDENCE_RULES, response_policy, update_focus
from conversation_state import empty_state


class CollaborationFocusTests(unittest.TestCase):
    def test_empty_focus_starts_undecided(self):
        focus = empty_focus()

        self.assertEqual("undecided", focus["design_stage"]["value"])
        self.assertEqual("undecided", focus["task_focus"]["value"])
        self.assertEqual("undecided", focus["external_context_priority"]["value"])
        self.assertEqual({}, focus["pending_switch"])

    def test_vague_early_brief_requests_one_natural_focus_question(self):
        state = update_focus(empty_state(), "老师让我设计一个大学生活动中心，但我现在没有思路。", 1)

        self.assertEqual("early_concept", state["collaboration_focus"]["design_stage"]["value"])
        self.assertEqual("undecided", state["collaboration_focus"]["task_focus"]["value"])
        policy = response_policy(state)
        self.assertIn("自然追问最多一个问题", policy)
        self.assertIn("0 个合法", policy)
        self.assertIn("不要生成按钮", policy)

    def test_any_modifier_before_no_idea_still_means_early_concept(self):
        state = update_focus(empty_state(), "老师让我设计大学生活动中心，但我现在没有任何思路。", 1)

        self.assertEqual("early_concept", state["collaboration_focus"]["design_stage"]["value"])
        policy = response_policy(state)
        self.assertIn("本轮只判断作业重点", policy)
        self.assertIn("直接询问老师是否要求具体场地回应", policy)

    def test_student_can_confirm_building_body_priority(self):
        state = update_focus(empty_state(), "没有具体场地，老师让我们先把建筑本身做出来。", 2)
        focus = state["collaboration_focus"]

        self.assertEqual("early_concept", focus["design_stage"]["value"])
        self.assertEqual("building_body", focus["task_focus"]["value"])
        self.assertEqual("deferred", focus["external_context_priority"]["value"])
        self.assertEqual("confirmed", focus["task_focus"]["status"])
        self.assertIn("可画的空间骨架", response_policy(state))
        self.assertIn("不要反复索要场地", response_policy(state))
        self.assertIn("不要强迫学生在可融合内容中二选一", response_policy(state))
        self.assertIn("示范性起点", response_policy(state))
        self.assertIn("接受、修改、组合或完全放弃", response_policy(state))
        self.assertIn("不得默认学生已经接受", response_policy(state))
        self.assertIn("不必以问题收尾", response_policy(state))
        self.assertIn("不得用两个预设体验或形式做封闭二选一", response_policy(state))
        self.assertIn("输出前检查结尾", response_policy(state))

    def test_evidence_policy_keeps_observation_and_inference_separate(self):
        state = update_focus(empty_state(), "我已经有任务书和场地资料，请帮我分析入口。", 1)
        policy = response_policy(state)

        self.assertIn("区分五类信息", policy)
        self.assertIn("可观察信息", policy)
        self.assertIn("成立条件和待验证因素", policy)
        self.assertIn("不得使用", policy)
        self.assertIn("不把方向与价值角色绑定", policy)
        self.assertIn("条件化比较必须对不同方向保持对称", policy)
        self.assertIn("最多 2-3 条", policy)
        self.assertIn("建筑推进量", policy)
        self.assertIn("不得把‘让学生去画’本身视为完成设计推进", policy)
        self.assertIn("不得编造场景", policy)

    def test_general_evidence_rules_apply_across_all_paths(self):
        # V1.0：证据分层贯穿所有路径，不依赖 evidence_development 阶段或上传资料
        state = update_focus(empty_state(), "老师让我设计大学生活动中心，但我现在没有思路。", 1)
        policy = response_policy(state)
        self.assertIn("区分五类信息", policy)
        self.assertIn("不把方向与价值角色绑定", policy)

    @unittest.skip("V1.0 后四栏硬编码与北/南词表过滤已移除，保留此测试作为历史记录")
    def test_boundary_editor_removes_directional_judgments_from_four_columns(self):
        state = update_focus(empty_state(), "我已经有任务书和场地资料，请帮我分析入口。", 1)
        policy = response_policy(state)
        draft = """1. 可确认的项目事实
- 北侧为校园主路。

2. AI 可以做的观察
- 北侧临校园主路，通常承担主要人流来向。
- 南侧为多层教学楼，存在潜在噪声源。

3. AI 只能提出的推测
- 这是推测：北侧入口可达性更高。
- 这是推测：南侧入口采光更佳。

4. 需要学生自己决定或补充证据的问题
- 是面向全校的公共客厅（可能倾向北侧），还是与教学楼形成教学组团（可能倾向南侧）？
"""
        revised = _enforce_response_boundaries(draft, policy)

        self.assertIn("现有资料不足以直接判断北侧或南侧哪一个更优", revised)
        self.assertNotIn("通常承担主要人流", revised)
        self.assertNotIn("潜在噪声源", revised)
        self.assertNotIn("可达性更高", revised)
        self.assertNotIn("采光更佳", revised)
        self.assertNotIn("公共客厅", revised)
        self.assertNotIn("教学组团", revised)
        self.assertIn("评价标准比较入口方向", revised)

    def test_new_site_requirement_proposes_switch_without_overwriting(self):
        state = update_focus(empty_state(), "没有具体场地，先把建筑本身做出来。", 1)
        state = update_focus(state, "老师后来给了校园入口旁的具体基地，要求处理入口人流和周边关系。", 2)
        focus = state["collaboration_focus"]

        self.assertEqual("building_body", focus["task_focus"]["value"])
        self.assertEqual("integrated", focus["pending_switch"]["task_focus"])
        self.assertEqual("primary", focus["pending_switch"]["external_context_priority"])
        self.assertIn("只说明一次", response_policy(state))
        self.assertIn("不得在确认前宣称外部条件已成为首要约束", response_policy(state))

    def test_student_confirmation_applies_pending_switch_and_records_change(self):
        state = update_focus(empty_state(), "没有具体场地，先把建筑本身做出来。", 1)
        state = update_focus(state, "老师给了具体基地，要求回应入口人流和周边关系。", 2)
        state = update_focus(state, "可以，就按建筑和场地综合推进。", 3)
        focus = state["collaboration_focus"]

        self.assertEqual("integrated", focus["task_focus"]["value"])
        self.assertEqual("primary", focus["external_context_priority"]["value"])
        self.assertEqual({}, focus["pending_switch"])
        self.assertEqual("task_focus", state["change_log"][-1]["dimension"])
        self.assertEqual("building_body", state["change_log"][-1]["from"])
        self.assertEqual("integrated", state["change_log"][-1]["to"])
        self.assertIn("不要为了凑数量强行拆成三个方向", response_policy(state))

    def test_unchanged_focus_does_not_request_repeated_mode_statement(self):
        state = update_focus(empty_state(), "没有具体场地，先把建筑本身做出来。", 1)
        state = update_focus(state, "我想先组织入口大厅、社团活动和安静学习空间。", 2)

        self.assertEqual({}, state["collaboration_focus"]["pending_switch"])
        self.assertIn("不要重复声明当前模式", response_policy(state))

    def test_existing_scheme_uses_review_policy_under_current_focus(self):
        state = update_focus(empty_state(), "没有具体场地，先把建筑本身做出来。", 1)
        state = update_focus(state, "这是我的第一版平面方案，请帮我评图。", 2)

        self.assertEqual("review_revision", state["collaboration_focus"]["design_stage"]["value"])
        policy = response_policy(state)
        self.assertIn("按当前作业重点评图", policy)
        self.assertIn("不得因缺少非重点资料直接判失败", policy)

    def test_full_conversation_can_move_from_building_body_to_integrated(self):
        state = update_focus(empty_state(), "老师让我设计大学生活动中心，但我没有思路。", 1)
        self.assertEqual("undecided", state["collaboration_focus"]["task_focus"]["value"])

        state = update_focus(state, "没有具体场地，老师让我们先把建筑本身做出来。", 2)
        self.assertEqual("building_body", state["collaboration_focus"]["task_focus"]["value"])

        state = update_focus(state, "老师后来给了校园入口旁的具体基地，要求回应入口人流和周边关系。", 3)
        self.assertEqual("building_body", state["collaboration_focus"]["task_focus"]["value"])
        self.assertEqual("integrated", state["collaboration_focus"]["pending_switch"]["task_focus"])

        state = update_focus(state, "可以，就按建筑和场地综合推进。", 4)
        self.assertEqual("integrated", state["collaboration_focus"]["task_focus"]["value"])
        self.assertEqual({}, state["collaboration_focus"]["pending_switch"])
        self.assertEqual(1, len([item for item in state["change_log"] if item.get("dimension") == "task_focus"]))


if __name__ == "__main__":
    unittest.main()
