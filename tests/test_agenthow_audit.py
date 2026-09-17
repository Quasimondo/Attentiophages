"""Tests for the analysis half of tools/agenthow_audit.py on a synthetic fetch."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from agenthow_audit import OURS, analyse  # noqa: E402


def synthetic() -> dict:
    export = [
        {"id": "n1", "origin": "https://agenthow.to/notes/n1", "kind": "note", "author": "a-ilands",
         "actor_id": "a_1", "topic": "outside money", "basis": "Contributor report", "created_at": "2026-09-15T00:00:00Z"},
        {"id": "n2", "origin": "https://agenthow.to/notes/n2", "kind": "request", "author": "b-ilands",
         "actor_id": "a_2", "topic": "data & research", "basis": "Contributor report", "created_at": "2026-09-16T00:00:00Z"},
        {"id": "n3", "origin": "https://agenthow.to/notes/n3", "kind": "note", "author": "Codex",
         "actor_id": "a_3", "topic": "", "basis": "Archive excerpt · assembled by Codex", "created_at": "2026-09-09T00:00:00Z"},
    ]
    actors = {
        "a_1": {"identity": "self-declared", "profile": {"platform": "iLands"}},
        "a_2": {"identity": "self-declared", "profile": {}},
        "a_3": None,
    }
    reports = {"n1": [], "n2": [{"author": "c", "outcome": "worked"}, {"author": "d", "outcome": "worked"}], "n3": None}
    return {"export": export, "requests_open": [export[1]], "stats": {"totals": {"posts": 300, "entities": 150}},
            "actors": actors, "reports": reports}


class TestAnalyse(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.r = analyse(synthetic())

    def test_counts(self) -> None:
        r = self.r
        self.assertEqual((r["export_records"], r["notes"], r["requests"], r["requests_open"]), (3, 2, 1, 1))
        self.assertEqual(r["month_posts_per_stats"], 300)
        self.assertEqual(r["seeded_by_codex"], 1)

    def test_identity_and_platform_declarations(self) -> None:
        self.assertEqual(self.r["identity_declared"], {"self-declared": 2, "(no profile)": 1})
        self.assertEqual(dict(self.r["platforms_declared"]), {"iLands": 1, "(undeclared)": 2})

    def test_reports_are_counted_from_the_per_note_fetch_not_the_export(self) -> None:
        r = self.r
        self.assertEqual(r["outcome_reports"], 2)
        self.assertEqual(r["notes_with_reports"], 1)
        self.assertEqual(r["distinct_reporters"], 2)
        self.assertEqual(r["report_verdicts"], {"worked": 2})

    def test_topics_treat_blank_as_none(self) -> None:
        self.assertIn(("(none)", 1), self.r["topics"])

    def test_our_record_origins_are_on_the_hub(self) -> None:
        for ref in OURS.values():
            origin = ref[0] if isinstance(ref, tuple) else ref
            self.assertTrue(origin.startswith("https://agenthow.to/notes/n_"))


if __name__ == "__main__":
    unittest.main()
