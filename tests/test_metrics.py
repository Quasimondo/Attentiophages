"""Tests for attentiophages.metrics.

These assert behaviour that the v1 implementation claimed but never had: that
the metrics actually distinguish the agent archetypes the framework describes.
"""

from __future__ import annotations

import unittest

from attentiophages.metrics import (
    Corpus,
    Post,
    Unavailable,
    _percentiles,
    agent_quality,
    amplification_edges,
    attention_units,
    credibility_divergence,
    detect_coalitions,
    network_impact,
)

DAY = 86_400.0
BASE = 1_700_000_000.0


def posts(author: str, n: int, quality: float, *, start: float = BASE,
          text: str = "some ordinary text about a topic", hour_step: float = 3600.0,
          mentions: tuple[str, ...] = ()) -> list[Post]:
    return [
        Post(
            id=f"{author}-{i}",
            author=author,
            timestamp=start + i * hour_step,
            text=f"{text} {i}",
            mentions=mentions,
            scores={"quality": quality},
        )
        for i in range(n)
    ]


class TestAgentQuality(unittest.TestCase):
    def test_shrinkage_penalises_thin_records(self) -> None:
        corpus = Corpus(
            posts("prolific", 20, 9.0)
            + posts("oneshot", 1, 10.0)
            + posts("filler", 20, 5.0)
        )
        quality = agent_quality(corpus)
        self.assertGreater(quality["prolific"], quality["oneshot"])

    def test_unscored_agents_are_omitted_not_defaulted(self) -> None:
        corpus = Corpus(
            posts("scored", 3, 7.0)
            + [Post(id="x", author="unscored", timestamp=BASE, text="hi")]
        )
        quality = agent_quality(corpus)
        self.assertIn("scored", quality)
        self.assertNotIn("unscored", quality)


class TestAmplificationEdges(unittest.TestCase):
    def test_replies_and_mentions_count_self_edges_do_not(self) -> None:
        corpus = Corpus(
            [
                Post(id="a1", author="alice", timestamp=BASE, text="root"),
                Post(id="b1", author="bob", timestamp=BASE, parent_id="a1"),
                Post(id="b2", author="bob", timestamp=BASE, mentions=("alice",)),
                Post(id="b3", author="bob", timestamp=BASE, mentions=("bob",)),
            ]
        )
        edges = amplification_edges(corpus)
        self.assertEqual(edges[("bob", "alice")], 2.0)
        self.assertNotIn(("bob", "bob"), edges)

    def test_mentions_of_unknown_agents_are_ignored(self) -> None:
        corpus = Corpus([Post(id="a1", author="alice", timestamp=BASE,
                              mentions=("ghost",))])
        self.assertEqual(amplification_edges(corpus), {})


def _ecosystem() -> Corpus:
    """Good agents, spam agents, a credibility farmer and a quiet curator."""
    everything: list[Post] = []
    for name in ("goodA", "goodB", "goodC"):
        everything += posts(name, 10, 9.0)
    for name in ("spamA", "spamB", "spamC"):
        everything += posts(name, 10, 1.0)

    # High-quality posts, but amplifies only the spam accounts.
    everything += posts("farmer", 10, 9.0, mentions=("spamA", "spamB", "spamC"))
    # Middling posts, but amplifies only the good accounts.
    everything += posts("curator", 10, 5.0, mentions=("goodA", "goodB", "goodC"))
    return Corpus(everything)


class TestNetworkImpact(unittest.TestCase):
    def test_amplifying_spam_scores_negative(self) -> None:
        impact = network_impact(_ecosystem())
        self.assertLess(impact["farmer"].total, 0.0)
        self.assertLess(impact["farmer"].mean, 0.0)

    def test_amplifying_quality_scores_positive(self) -> None:
        impact = network_impact(_ecosystem())
        self.assertGreater(impact["curator"].total, 0.0)
        self.assertGreater(impact["curator"].mean, 0.0)

    def test_mean_normalises_for_volume(self) -> None:
        """A selective amplifier should not lose to a prolific one on mean."""
        base = list(_ecosystem().posts)
        base += posts("loud", 30, 5.0, mentions=("goodA",))
        base += posts("quiet", 3, 5.0, mentions=("goodA",))
        impact = network_impact(Corpus(base))
        self.assertGreater(impact["loud"].total, impact["quiet"].total)
        self.assertAlmostEqual(impact["loud"].mean, impact["quiet"].mean, places=6)

    def test_targets_without_scores_contribute_nothing(self) -> None:
        corpus = Corpus(
            posts("rater", 5, 5.0, mentions=("mystery",))
            + [Post(id="m0", author="mystery", timestamp=BASE, text="no scores")]
        )
        impact = network_impact(corpus)
        self.assertNotIn("rater", impact)


class TestCredibilityDivergence(unittest.TestCase):
    def test_farmer_diverges_positive_curator_negative(self) -> None:
        divergence = credibility_divergence(_ecosystem())
        self.assertGreater(divergence["farmer"], 0.0)
        self.assertLess(divergence["curator"], 0.0)
        self.assertGreater(divergence["farmer"], divergence["curator"])

    def test_agents_without_enough_edges_are_unavailable(self) -> None:
        divergence = credibility_divergence(_ecosystem())
        self.assertIsInstance(divergence["goodA"], Unavailable)

    def test_unavailable_result_refuses_to_be_used_as_a_number(self) -> None:
        divergence = credibility_divergence(_ecosystem())
        with self.assertRaises(TypeError):
            float(divergence["goodA"])
        with self.assertRaises(TypeError):
            _ = divergence["goodA"] + 1


class TestCoalitionDetection(unittest.TestCase):
    def _corpus(self) -> Corpus:
        everything: list[Post] = []
        template = "buy now limited offer act fast do not miss this once in a lifetime"
        for i in range(1, 6):
            everything += posts(
                f"coalition_node_{i:03d}", 8, 1.0,
                text=template, hour_step=0.0, start=BASE + i,
            )
        for name in ("alice", "bob", "carol"):
            everything += posts(name, 8, 7.0, text=f"{name} writes distinct prose here",
                                hour_step=7000.0)
        return Corpus(everything)

    def test_finds_the_named_cluster(self) -> None:
        found = detect_coalitions(self._corpus())
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].stem, "coalition_node")
        self.assertEqual(found[0].size, 5)

    def test_template_reuse_shows_as_high_text_similarity(self) -> None:
        found = detect_coalitions(self._corpus())
        self.assertGreater(found[0].text_similarity, 0.5)

    def test_shared_schedule_shows_as_high_timing_similarity(self) -> None:
        found = detect_coalitions(self._corpus())
        self.assertGreater(found[0].timing_similarity, 0.9)

    def test_unrelated_agents_do_not_cluster(self) -> None:
        found = detect_coalitions(self._corpus())
        members = {m for c in found for m in c.members}
        self.assertNotIn("alice", members)


class TestPercentiles(unittest.TestCase):
    def test_ties_share_the_midpoint(self) -> None:
        result = _percentiles({"a": 1.0, "b": 1.0, "c": 2.0})
        self.assertEqual(result["a"], result["b"])
        self.assertGreater(result["c"], result["a"])

    def test_single_value_is_midpoint(self) -> None:
        self.assertEqual(_percentiles({"only": 3.0}), {"only": 0.5})

    def test_empty_input(self) -> None:
        self.assertEqual(_percentiles({}), {})


class TestAttentionUnitsRefusesToGuess(unittest.TestCase):
    def test_returns_unavailable_with_a_reason(self) -> None:
        result = attention_units(Corpus(posts("alice", 3, 5.0)))
        self.assertIsInstance(result, Unavailable)
        self.assertIn("dwell time", result.reason)

    def test_cannot_be_silently_used_in_arithmetic(self) -> None:
        result = attention_units(Corpus(posts("alice", 3, 5.0)))
        for operation in (
            lambda: result * 2,
            lambda: 2 * result,
            lambda: result / 2,
            lambda: bool(result),
            lambda: result > 1,
        ):
            with self.assertRaises(TypeError):
                operation()


if __name__ == "__main__":
    unittest.main()
