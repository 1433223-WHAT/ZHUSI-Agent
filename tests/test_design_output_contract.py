"""测试设计协助请求的输出契约（V1.2 空转治理）。

背景：2026-08-19 真实对话中，学生说"帮我设计一下/给我一个框架/一半一半"后，
AI 连续四轮拆问题（动/静→自习/阅览→怎么到达→一个入口还是两个入口）从不落地。
本测试锁定三个机制：① 设计请求被识别为 design_request 并注入骨架产出策略；
② "给我框架"得到的是设计框架（骨架）而非思考步骤；③ 学生给出明确偏好时
不被 clarify/request_vision 拦截，直接走模型产出。

修复前这些断言全部失败；修复后应全部通过。
"""

import unittest
from unittest.mock import patch

from architect_chat import chat_turn, classify_intent
from conversation_state import empty_state


class DesignOutputContractTests(unittest.TestCase):
    def _policy_arg(self, mock_call):
        """_call_deepseek 的第 6 个位置参数是 policy（本轮回答策略）。"""
        args = mock_call.call_args[0]
        return args[5]

    @patch("architect_chat._call_deepseek")
    def test_A_design_request_must_output_skeleton_policy(self, mock_call):
        """测试 A：'你可以帮我设计一下吗' 必须注入骨架产出策略，不能退回继续提问。"""
        mock_call.return_value = "示范骨架：入口与公共活动放前部，中部检索借阅核心，后部自习阅览……"

        result = chat_turn("你可以帮我设计一下吗", [], empty_state())

        self.assertEqual("design_request", result["intent"])
        policy = self._policy_arg(mock_call)
        self.assertIn("示范性空间骨架", policy, "policy 必须要求输出示范骨架")
        self.assertIn("可以接受、修改、组合或完全放弃", policy, "骨架必须声明可修改")
        self.assertNotIn("最后问题应开放询问", policy, "不再强制以问题结尾")
        self.assertEqual(mock_call.return_value, result["reply"], "骨架回复应直接透传，不被改写拦截")

    @patch("architect_chat._call_deepseek")
    def test_B_framework_request_is_design_framework_not_thinking_steps(self, mock_call):
        """测试 B：'我需要你给我一个框架' 应得到设计框架（空间骨架），而非思考步骤清单。"""
        mock_call.return_value = "设计框架：入口缓冲 → 公共活动 → 检索借阅核心 → 自习/阅览分区 → 儿童活动靠入口侧……"

        result = chat_turn("我需要你给我一个框架", [], empty_state())

        self.assertEqual("design_request", result["intent"])
        policy = self._policy_arg(mock_call)
        self.assertIn("空间组织骨架", policy, "框架必须是空间组织骨架")
        self.assertNotIn("第一层思考什么", policy)

    @patch("architect_chat.router_classify", return_value=None)
    @patch("architect_chat._call_deepseek")
    def test_C_explicit_preference_converges_to_output_not_question(self, mock_call, mock_router):
        """测试 C：前面已知自习/阅览各一半，'一半一半' 是明确偏好，应直接产出第一版，不再问'一个入口还是两个入口'。"""
        state = empty_state()
        state["project"]["functions"] = {
            "value": "自习区、阅览区（各半）", "status": "confirmed", "source": "student",
            "evidence": "自习和阅览各一半", "turn_id": 1,
        }
        state["student_decisions"] = [{"value": "自习和阅览各一半", "turn_id": 1, "source": "student"}]
        mock_call.return_value = "好，那我先按各半给你摆一版：静区内部自习与阅览各占一半，中间用书库缓冲……"

        result = chat_turn("一半一半", [], state, turn_id=2)

        # 明确偏好不应被澄清/引导上传拦截 → 必须走到模型
        self.assertEqual("general_architecture_chat", result["intent"])
        self.assertTrue(result["model_called"], "明确偏好时不应被 clarify/request_vision 拦截")
        self.assertEqual("ok", result["model_status"])
        self.assertEqual(mock_call.return_value, result["reply"], "应直接产出骨架而不是返回澄清问题")


if __name__ == "__main__":
    unittest.main()
