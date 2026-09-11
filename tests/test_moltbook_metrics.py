"""Tests for the analysis half of tools/moltbook_metrics.py on a synthetic corpus."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from attentiophages.metrics import Corpus, Post  # noqa: E402
from moltbook_metrics import MENTION, _ts, analyse  # noqa: E402


def synthetic() -> Corpus:
    posts = []
    t = 1_700_000_000.0
    # a numeric-suffix cluster of 4, decent quality
    for i in range(4):
        for k in range(3):
            posts.append(Post(id=f"cn{i}-{k}", author=f"coalition_node_{i:03d}", timestamp=t + i * 60 + k,
                              text=f"different text {i} {k} about topic number {i * k}", scores={"quality": 7.0}))
    # a promotion family: good posts, all mentioning two bad accounts
    for name in ("Fam-Alpha", "Fam-Beta", "Fam-Gamma"):
        for k in range(4):
            posts.append(Post(id=f"{name}-{k}", author=name, timestamp=t + 3600 * k,
                              text=f"explainer {k} @BadOne @BadTwo", mentions=("BadOne", "BadTwo"),
                              scores={"quality": 6.0}))
    for name in ("BadOne", "BadTwo"):
        posts.append(Post(id=f"{name}-p", author=name, timestamp=t, text="$TOKEN", scores={"quality": 1.0}))
    # background population
    for i in range(20):
        posts.append(Post(id=f"bg{i}", author=f"agent{i}x", timestamp=t + i * 7200, text=f"post {i}",
                          scores={"quality": 3.0 + (i % 5)}))
    posts.append(Post(id="c:1", author="agent1x", timestamp=t, text="reply", parent_id="bg2"))
    return Corpus(posts)


class TestAnalyse(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = analyse(synthetic(), {"posts": 0})

    def test_coalition_node_found_and_ranked(self) -> None:
        cn = self.result["coalition_node"]
        self.assertEqual(cn["size"], 4)
        self.assertEqual(cn["size_rank_among_stems"], 1)
        self.assertIsInstance(cn["text_rank_among_stems"], int)

    def test_promotion_family_tops_credibility_divergence(self) -> None:
        top = [row[0] for row in self.result["credibility_divergence"]["top_positive"]]
        self.assertEqual(set(top[:3]), {"Fam-Alpha", "Fam-Beta", "Fam-Gamma"})

    def test_family_without_numeric_suffix_is_not_a_stem(self) -> None:
        stems = {row[0] for row in self.result["top_stems_by_size"]}
        self.assertNotIn("Fam", stems)
        self.assertIn("coalition_node", stems)

    def test_curators_absent_are_reported_not_invented(self) -> None:
        for info in self.result["curators"].values():
            self.assertEqual(info["posts"], 0)
            self.assertIsNone(info["quality"])
            self.assertEqual(info["divergence"], "not in corpus")

    def test_graph_counts(self) -> None:
        g = self.result["graph"]
        self.assertEqual(g["edges"], 3 * 2 + 1)   # family -> two targets, plus one comment reply
        self.assertEqual(g["sources_with_out_weight_ge_3"], 3)


class TestHelpers(unittest.TestCase):
    def test_mention_regex_resolves_handles_not_emails_or_versions(self) -> None:
        self.assertEqual(MENTION.findall("thanks @KingMolt and @Some-Agent_1"), ["KingMolt", "Some-Agent_1"])
        self.assertEqual(MENTION.findall("openssl@3 mail me at a@b.com"), [])

    def test_timestamp_parsing(self) -> None:
        self.assertGreater(_ts("2026-01-31T01:27:19.326849+00:00"), 1_700_000_000)
        self.assertEqual(_ts(None), 0.0)
        self.assertEqual(_ts("not a date"), 0.0)


if __name__ == "__main__":
    unittest.main()
