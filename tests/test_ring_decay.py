"""Tests for tools/ring_decay.py: the decay curves are analytic, so pin them."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from ring_decay import BUY, MINT, SELF_DEALS, build  # noqa: E402
from swarm.irc_rendezvous import CRYPTO_AVAILABLE  # noqa: E402


@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography not installed")
class TestBuy(unittest.TestCase):
    def test_no_cover_is_the_docs06_ring(self) -> None:
        r = build(BUY, 0)
        self.assertAlmostEqual(r.ring_concentration, 1.0)
        self.assertTrue(r.ring_isolated)
        self.assertEqual(r.ring_rank_plain, 1)

    def test_one_real_counterparty_ends_isolation(self) -> None:
        self.assertFalse(build(BUY, 1).ring_isolated)

    def test_concentration_reaches_parity_at_one_cover_job_per_self_deal(self) -> None:
        # 6 self-deals plus 6 cover jobs spread evenly over 3 workers:
        # HHI = (6^2 + 3 * 2^2) / 12^2 = 48 / 144 = 1/3, the honest posters' value.
        r = build(BUY, SELF_DEALS)
        self.assertAlmostEqual(r.ring_concentration, 1 / 3)
        self.assertAlmostEqual(r.honest_concentration, 1 / 3)

    def test_ratings_advantage_survives_all_cover(self) -> None:
        for m in (0, 6, 12):
            r = build(BUY, m)
            self.assertEqual((r.ring_rank_plain, r.ring_rank_by_rater), (1, 1), m)

    def test_cover_costs_budget_not_keys(self) -> None:
        r = build(BUY, 4)
        self.assertGreater(r.cost_budgets, 0)
        self.assertEqual(r.cost_keys, 0)


@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography not installed")
class TestMint(unittest.TestCase):
    def test_sybils_keep_the_ring_isolated_until_it_outgrows_the_market(self) -> None:
        self.assertTrue(build(MINT, 4).ring_isolated)     # 6 ring keys vs 6 honest agents
        r = build(MINT, 5)                                 # 7 vs 6: the ring is now "main"
        self.assertFalse(r.ring_isolated)
        self.assertTrue(r.ring_is_largest)

    def test_sybils_cost_keys_not_budget(self) -> None:
        r = build(MINT, 5)
        self.assertEqual(r.cost_budgets, 0)
        self.assertEqual(r.cost_keys, 5)

    def test_concentration_decays_the_same_either_way(self) -> None:
        self.assertAlmostEqual(build(MINT, 3).ring_concentration, build(BUY, 3).ring_concentration)

    def test_unknown_strategy_refused(self) -> None:
        with self.assertRaises(ValueError):
            build("borrow", 1)


if __name__ == "__main__":
    unittest.main()
