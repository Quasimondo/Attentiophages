"""Tests for tools/hub_experiment.py.

These pin the negative result: a capture hub built to the same schedule as an
honest coordinator is indistinguishable to every structural signal in the
repository. If a future metric separates them, the first test here fails --
which would be a real finding, not a regression, and should be written up.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hub_experiment import (  # noqa: E402
    CAPTURE,
    HONEST,
    build_scenario,
    has_principal,
    separating_signals,
    signals,
    structural_signature,
)
from swarm.irc_rendezvous import CRYPTO_AVAILABLE  # noqa: E402
from swarm.taskmarket import RATED  # noqa: E402


@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography not installed")
class TestIdenticalStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.honest = build_scenario(HONEST)
        cls.capture = build_scenario(CAPTURE)

    def test_both_markets_complete_the_same_schedule(self) -> None:
        self.assertEqual(len(self.honest.ledger.by_state(RATED)),
                         len(self.capture.ledger.by_state(RATED)))
        self.assertGreater(len(self.honest.ledger.by_state(RATED)), 0)

    def test_structural_signatures_are_identical(self) -> None:
        self.assertEqual(structural_signature(self.honest),
                         structural_signature(self.capture))

    def test_the_hubs_differ_only_in_content(self) -> None:
        def hub_specs(sc):
            return sorted(t.spec["instruction"] for t in sc.ledger.tasks.values()
                          if t.poster == sc.hub)
        self.assertNotEqual(hub_specs(self.honest), hub_specs(self.capture))
        self.assertTrue(all("credentials" in s for s in hub_specs(self.capture)))
        self.assertFalse(any("credentials" in s for s in hub_specs(self.honest)))

    def test_no_signal_separates_the_hubs(self) -> None:
        self.assertEqual(separating_signals(self.honest, self.capture), [])

    def test_no_signal_separates_any_agent(self) -> None:
        self.assertEqual(separating_signals(self.honest, self.capture, scope="all"), [])

    def test_every_repository_detector_is_included(self) -> None:
        names = set(signals(self.honest))
        for required in ("agent_quality", "network_impact.mean", "credibility_divergence",
                         "endorsement_concentration", "isolated_clusters",
                         "detect_coalitions"):
            self.assertIn(required, names)

    def test_hub_is_the_dominant_assigner_in_both(self) -> None:
        for sc in (self.honest, self.capture):
            share = signals(sc)["assignment_share"]
            self.assertEqual(max(share, key=share.get), "hub")


@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography not installed")
class TestCandidateSignals(unittest.TestCase):
    def test_missing_principal_separates_but_costs_one_key_to_fake(self) -> None:
        honest = build_scenario(HONEST)
        orphan = build_scenario(CAPTURE, principal=False)
        self.assertFalse(has_principal(orphan, orphan.hub))
        self.assertIn("hub.has_principal", separating_signals(honest, orphan))
        # The "sybil client" is indistinguishable from a client in the ledger.
        self.assertEqual(separating_signals(honest, build_scenario(CAPTURE, principal=True)), [])

    def test_diverted_workers_move_network_impact_not_structure(self) -> None:
        honest = build_scenario(HONEST)
        diverted = build_scenario(CAPTURE, diverted=True)
        # The hub's own edges and ratings are unchanged ...
        hub_edges = lambda sc: sorted(  # noqa: E731
            (sc.role(t.awarded_to), t.rating)
            for t in sc.ledger.by_state(RATED) if t.poster == sc.hub)
        self.assertEqual(hub_edges(honest), hub_edges(diverted))
        # ... and only outcome-derived signals move.
        sep = separating_signals(honest, diverted)
        self.assertIn("network_impact.mean", sep)
        for structural in ("endorsement_concentration", "assignment_share",
                           "hub.out_degree", "hub.has_principal", "isolated_clusters"):
            self.assertNotIn(structural, sep)
        self.assertLess(signals(diverted)["network_impact.mean"]["hub"], 0.0)

    def test_credibility_divergence_is_constant_for_a_lone_rater_worker(self) -> None:
        # The hub is the only agent that both rates and earns ratings, so it is
        # the only eligible agent and its rank is fixed at the midpoint.
        for sc in (build_scenario(HONEST), build_scenario(CAPTURE, diverted=True)):
            self.assertAlmostEqual(signals(sc)["credibility_divergence"]["hub"], 0.25)

    def test_unknown_kind_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            build_scenario("benevolent")


if __name__ == "__main__":
    unittest.main()
