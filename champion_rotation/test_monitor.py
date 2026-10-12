"""Deterministic transition tests without network or brokerage access."""
import unittest
import pandas as pd
from champion_rotation.monitor import transition

class TransitionTests(unittest.TestCase):
    def test_c_waits_for_three_confirmations(self):
        rank = pd.Series([15.0, 8.0], index=["NEW", "OLD"])
        old = {"target": "OLD", "candidate": None, "streak": 0, "date": "2026-10-07"}
        old, msg = transition(old, rank, "C", "2026-10-08", False)
        self.assertIn("1/3", msg)
        old, msg = transition(old, rank, "C", "2026-10-09", False)
        self.assertIn("2/3", msg)
        old, msg = transition(old, rank, "C", "2026-10-12", False)
        self.assertIn("TARGET CHANGE", msg)
        self.assertEqual(old["target"], "NEW")

    def test_no_duplicate_same_day(self):
        old = {"target": "OLD", "candidate": "NEW", "streak": 2, "date": "2026-10-09"}
        rank = pd.Series([15.0, 8.0], index=["NEW", "OLD"])
        state, msg = transition(old, rank, "C", "2026-10-09", False)
        self.assertEqual(state, old)
        self.assertEqual(msg, "ALREADY CHECKED")

    def test_buffer_blocks_switch(self):
        rank = pd.Series([12.9, 8.0], index=["NEW", "OLD"])
        old = {"target": "OLD", "candidate": None, "streak": 0, "date": "2026-10-07"}
        state, msg = transition(old, rank, "C", "2026-10-08", False)
        self.assertEqual(state["target"], "OLD")
        self.assertEqual(msg, "HOLD TARGET")

    def test_d_only_checks_mondays(self):
        rank = pd.Series([20.0, 9.0], index=["NEW", "OLD"])
        old = {"target": "OLD", "date": "2026-10-08"}
        state, msg = transition(old, rank, "D", "2026-10-09", True)
        self.assertEqual(state["target"], "OLD")
        state, msg = transition(state, rank, "D", "2026-10-12", True)
        self.assertEqual(state["target"], "NEW")
        self.assertIn("TARGET CHANGE", msg)

if __name__ == "__main__":
    unittest.main()
