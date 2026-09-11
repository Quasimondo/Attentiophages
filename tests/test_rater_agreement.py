"""Tests for the analysis half of tools/rater_agreement.py.

The rating half needs a local Ollama and the Moltbook database and is not
tested here. The sample and the numbers it produced are in docs/11.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from rater_agreement import (  # noqa: E402
    BANDS,
    DIMENSIONS,
    PROMPTS,
    SCORE_RE,
    agreement,
    band,
    dimensions_for,
    pairs,
    parse_failures,
    spearman,
)


def make_state(rows):
    """rows: (post_id, original, retest, qwen35) per dimension dicts."""
    posts, ratings = [], {}
    for pid, orig, retest, q35 in rows:
        posts.append({"id": pid, "author": "a", "stratum": "s", "text": "", "original": orig})
        ratings[pid] = {
            "retest": {d: {"score": v, "raw": ""} for d, v in retest.items()},
            "qwen3.5": {d: {"score": v, "raw": ""} for d, v in q35.items()},
        }
    return {"posts": posts, "ratings": ratings}


class TestSpearman(unittest.TestCase):
    def test_perfect_and_inverse(self) -> None:
        self.assertAlmostEqual(spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(spearman([1, 2, 3, 4], [40, 30, 20, 10]), -1.0)

    def test_ties_share_a_rank(self) -> None:
        # Monotone but with ties: still perfectly rank-correlated.
        self.assertAlmostEqual(spearman([1, 1, 2, 3], [5, 5, 6, 7]), 1.0)

    def test_constant_input_is_undefined_not_zero(self) -> None:
        self.assertIsNone(spearman([3, 3, 3], [1, 2, 3]))

    def test_too_few_points_is_undefined(self) -> None:
        self.assertIsNone(spearman([1, 2], [2, 1]))


class TestBands(unittest.TestCase):
    def test_bands_cover_zero_to_ten_without_gaps(self) -> None:
        for dim in DIMENSIONS:
            covered = sorted(s for lo, hi in BANDS[dim] for s in range(lo, hi + 1))
            self.assertEqual(covered, list(range(11)), dim)

    def test_band_index(self) -> None:
        self.assertEqual(band("substance", 3), 0)
        self.assertEqual(band("substance", 4), 1)
        self.assertEqual(band("substance", 10), 2)
        self.assertEqual(band("manipulation", 5), 2)


class TestAgreement(unittest.TestCase):
    def test_pairs_skip_missing_scores(self) -> None:
        state = make_state([
            ("p1", {"substance": 5}, {"substance": 5}, {"substance": None}),
            ("p2", {"substance": 7}, {"substance": 8}, {"substance": 7}),
            ("p3", {}, {"substance": 2}, {"substance": 2}),
        ])
        self.assertEqual(pairs(state, "substance", "original", "retest"), [(5, 5), (7, 8)])
        self.assertEqual(pairs(state, "substance", "original", "qwen3.5"), [(7, 7)])
        self.assertEqual(pairs(state, "substance", "retest", "qwen3.5"), [(8, 7), (2, 2)])

    def test_agreement_statistics(self) -> None:
        state = make_state([
            ("p1", {"spam": 0}, {"spam": 1}, {}),
            ("p2", {"spam": 5}, {"spam": 5}, {}),
            ("p3", {"spam": 9}, {"spam": 7}, {}),
        ])
        a = agreement(state, "spam", "original", "retest")
        self.assertEqual(a["n"], 3)
        self.assertAlmostEqual(a["spearman"], 1.0)
        self.assertAlmostEqual(a["exact"], 1 / 3)
        self.assertAlmostEqual(a["within_1"], 2 / 3)
        self.assertAlmostEqual(a["same_band"], 1.0)   # 0/1 -> band 0, 5/5 -> 1, 9/7 -> 2

    def test_empty_comparison(self) -> None:
        self.assertEqual(agreement(make_state([]), "spam", "original", "retest"), {"n": 0})

    def test_parse_failures_counted_per_rater(self) -> None:
        state = make_state([
            ("p1", {"substance": 5}, {"substance": None}, {"substance": 4}),
            ("p2", {"substance": 5}, {"substance": None}, {"substance": None}),
        ])
        self.assertEqual(parse_failures(state), {"retest": 2, "qwen3.5": 1})


class TestPromptsAndParsing(unittest.TestCase):
    def test_prompts_have_the_content_slot_and_the_answer_format(self) -> None:
        for dim in DIMENSIONS:
            self.assertIn('"{content}"', PROMPTS[dim])
            self.assertIn("Score: X/10", PROMPTS[dim])

    def test_score_regex_matches_the_pipelines_format(self) -> None:
        self.assertEqual(SCORE_RE.search("Score: 7/10\nReason: fine").group(1), "7")
        self.assertEqual(SCORE_RE.search("Score:10 / 10").group(1), "10")
        self.assertIsNone(SCORE_RE.search("I would give this a 7."))

    def test_manipulation_is_rated_only_where_the_original_did(self) -> None:
        self.assertEqual(dimensions_for({"original": {"substance": 1, "spam": 2}}),
                         ("substance", "spam"))
        self.assertEqual(dimensions_for({"original": {"substance": 1, "manipulation": 0}}),
                         ("substance", "manipulation"))


if __name__ == "__main__":
    unittest.main()
