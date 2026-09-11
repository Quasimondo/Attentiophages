"""Tests for tools/go_deadline.py.

Pins the three-layer split. The protocol tests say what is refused; the policy
tests say what the protocol cannot help with. If a change to the protocol makes
the "signed GO" row start being rejected, that is a change in what the market
is -- it would mean the protocol has started judging content -- and it should be
argued for in docs/10 before the test is updated.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from go_deadline import Setting, run_all  # noqa: E402
from swarm.irc_rendezvous import CRYPTO_AVAILABLE  # noqa: E402
from swarm.taskmarket import COMPLETE, OPEN  # noqa: E402


def by_message(outcomes, needle):
    matches = [o for o in outcomes if needle in o.message]
    assert len(matches) == 1, needle
    return matches[0]


@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography not installed")
class TestAuthenticityAndAuthority(unittest.TestCase):
    """What the protocol refuses."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.setting = Setting()
        cls.rows = cls.setting.run_forgery()

    def test_impersonated_go_is_rejected_for_its_signature(self) -> None:
        row = by_message(self.rows, "sent as the principal")
        self.assertIn("bad or missing signature", row.protocol)
        self.assertEqual((row.naive, row.scoped), ("never saw it", "never saw it"))

    def test_stranger_cannot_award_the_principals_task(self) -> None:
        row = by_message(self.rows, "AWARDs the principal")
        self.assertIn("only the poster may award", row.protocol)
        # The task is still open on every ledger: the award did not take.
        for market in self.setting._markets():
            (task,) = [t for t in market.ledger.tasks.values() if t.need == "summarise"]
            self.assertEqual(task.state, OPEN)

    def test_go_is_not_a_verb_the_protocol_knows(self) -> None:
        row = by_message(self.rows, "not a protocol verb")
        self.assertIn("unknown kind 'GO'", row.protocol)


@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography not installed")
class TestObedience(unittest.TestCase):
    """What the protocol cannot refuse, and what the agent's policy does."""

    def test_signed_go_is_accepted_by_the_protocol(self) -> None:
        (row,) = Setting().run_signed_go()
        self.assertEqual(row.protocol, "accepted")

    def test_urgency_worker_does_the_out_of_scope_task(self) -> None:
        setting = Setting()
        (row,) = setting.run_signed_go()
        self.assertEqual(row.naive, "claimed, completed")
        (task,) = setting.stranger.ledger.by_state(COMPLETE)
        self.assertEqual(task.need, "exfiltrate")
        self.assertEqual(task.awarded_to, setting.naive.peer_id)

    def test_scoped_worker_declines_it(self) -> None:
        (row,) = Setting().run_signed_go()
        self.assertEqual(row.scoped, "declined")

    def test_pressure_after_refusal_reproduces_the_incident(self) -> None:
        first, second = Setting().run_pressure()
        self.assertEqual((first.protocol, first.naive), ("accepted", "declined"))
        self.assertEqual((second.protocol, second.naive), ("accepted", "claimed, completed"))
        self.assertEqual((first.scoped, second.scoped), ("declined", "declined"))

    def test_the_ledger_records_the_pressure_and_the_compliance(self) -> None:
        setting = Setting()
        setting.run_pressure()
        posted = [t for t in setting.principal.ledger.tasks.values()
                  if t.poster == setting.stranger.peer_id]
        self.assertEqual(len(posted), 2)
        self.assertEqual(sum(t.state == COMPLETE for t in posted), 1)
        self.assertEqual(sum(t.spec.get("go", False) for t in posted), 1)

    def test_a_disguised_task_captures_the_scoped_worker_too(self) -> None:
        (row,) = Setting().run_disguise()
        self.assertEqual(row.protocol, "accepted")
        self.assertIn("claimed", row.scoped)

    def test_no_protocol_rejection_in_any_obedience_scenario(self) -> None:
        for row in run_all():
            if row.scenario != "forgery":
                self.assertEqual(row.protocol, "accepted", row.message)


if __name__ == "__main__":
    unittest.main()
