import unittest

from candidate_route_ledger import (
    add_route,
    apply_user_route_response,
    build_generator_route_context,
    empty_route_ledger,
)


class CandidateRouteLedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = empty_route_ledger()
        self.route = add_route(
            self.ledger,
            statement="采用由浅入深的线性空间骨架",
            source="ai",
            turn_id=1,
        )

    def test_ai_route_starts_as_proposed(self):
        self.assertEqual("proposed", self.route["status"])
        self.assertEqual("ai", self.route["source"])

    def test_continue_to_explore_keeps_route_as_active_candidate(self):
        apply_user_route_response(
            self.ledger,
            "这个方向可以继续看看，帮我展开入口和流线。",
            turn_id=2,
        )
        self.assertEqual("active_candidate", self.route["status"])

    def test_develop_instruction_does_not_confirm_route(self):
        apply_user_route_response(
            self.ledger,
            "基于刚才方向继续深化。",
            turn_id=2,
        )
        self.assertEqual("active_candidate", self.route["status"])

    def test_new_project_fact_does_not_change_route_status(self):
        apply_user_route_response(
            self.ledger,
            "基地东侧有公园，北侧有道路。",
            turn_id=2,
        )
        self.assertEqual("proposed", self.route["status"])

    def test_rejection_removes_route_from_legal_generation(self):
        apply_user_route_response(
            self.ledger,
            "不要这个方向，换一个不依赖线性组织的骨架。",
            turn_id=2,
        )
        self.assertEqual("rejected", self.route["status"])
        context = build_generator_route_context(self.ledger)
        self.assertIn("不得复活", context)
        self.assertNotIn("【已确认设计前提】\n- 采用由浅入深", context)

    def test_explicit_commitment_confirms_only_referenced_atomic_route(self):
        derived = add_route(
            self.ledger,
            statement="主入口位于北侧",
            source="ai",
            turn_id=1,
            parent_id=self.route["id"],
        )
        apply_user_route_response(
            self.ledger,
            "我决定采用由浅入深的线性空间骨架。",
            turn_id=2,
        )
        self.assertEqual("confirmed", self.route["status"])
        self.assertEqual("proposed", derived["status"])

    def test_confirmed_and_candidate_routes_get_different_generator_permissions(self):
        apply_user_route_response(
            self.ledger,
            "基于刚才方向继续深化。",
            turn_id=2,
        )
        context = build_generator_route_context(self.ledger)
        self.assertIn("【可深化但未确认】", context)
        self.assertIn("只能作为测试分支", context)
        self.assertNotIn("【已确认设计前提】\n- 采用由浅入深", context)

    def test_suspended_route_is_not_an_active_premise(self):
        apply_user_route_response(
            self.ledger,
            "这个先放一放，我们先讨论场地边界。",
            turn_id=2,
        )
        self.assertEqual("suspended", self.route["status"])
        context = build_generator_route_context(self.ledger)
        self.assertIn("不得主动恢复", context)

    def test_ambiguous_pronoun_does_not_choose_between_multiple_routes(self):
        second = add_route(
            self.ledger,
            statement="采用中心放射的空间骨架",
            source="ai",
            turn_id=1,
        )
        apply_user_route_response(self.ledger, "就按这个做。", turn_id=2)
        self.assertEqual("proposed", self.route["status"])
        self.assertEqual("proposed", second["status"])
        self.assertEqual("ambiguous_reference", self.ledger["events"][-1]["action"])

    def test_developing_confirmed_route_does_not_demote_it(self):
        apply_user_route_response(
            self.ledger,
            "我决定采用由浅入深的线性空间骨架。",
            turn_id=2,
        )
        apply_user_route_response(
            self.ledger,
            "基于这个方向继续深化入口和流线。",
            turn_id=3,
        )
        self.assertEqual("confirmed", self.route["status"])

    def test_ordinary_continuation_language_activates_but_does_not_confirm(self):
        messages = (
            "这个还行，你接着弄。",
            "先照这个再往下推推。",
            "沿这个候选继续往下设计。",
            "这个可以，你再做具体一点。",
        )
        for message in messages:
            with self.subTest(message=message):
                ledger = empty_route_ledger()
                route = add_route(ledger, "采用中心放射骨架", "ai", 1)
                apply_user_route_response(ledger, message, turn_id=2)
                self.assertEqual("active_candidate", route["status"])

    def test_vague_acknowledgement_does_not_confirm_route(self):
        messages = ("嗯，行。", "这个听着还可以。", "然后呢？", "先这样看看。")
        for message in messages:
            with self.subTest(message=message):
                ledger = empty_route_ledger()
                route = add_route(ledger, "采用中心放射骨架", "ai", 1)
                apply_user_route_response(ledger, message, turn_id=2)
                self.assertNotEqual("confirmed", route["status"])

    def test_ordinary_reject_suspend_and_confirm_language(self):
        cases = (
            ("这个不太行，换一个。", "rejected"),
            ("先不聊这个，我们看场地。", "suspended"),
            ("就这么做吧，中心放射定下来。", "confirmed"),
        )
        for message, expected in cases:
            with self.subTest(message=message):
                ledger = empty_route_ledger()
                route = add_route(ledger, "采用中心放射骨架", "ai", 1)
                apply_user_route_response(ledger, message, turn_id=2)
                self.assertEqual(expected, route["status"])


if __name__ == "__main__":
    unittest.main()
