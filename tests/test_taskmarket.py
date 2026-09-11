"""Tests for swarm.taskmarket.

Most of these are adversarial. The protocol assumes participants are strangers,
so the interesting behaviour is what it refuses.
"""

from __future__ import annotations

import json
import unittest

from swarm.irc_rendezvous import CRYPTO_AVAILABLE, Identity, canonical
from swarm.taskmarket import (
    AWARDED,
    COMPLETE,
    OPEN,
    ProtocolError,
    RATED,
    TaskMarket,
    compute_task_id,
)
from swarm.transport import InMemoryBus, InMemoryTransport


def make_node(bus: InMemoryBus) -> TaskMarket:
    identity = Identity()
    return TaskMarket(InMemoryTransport(bus, identity.peer_id), identity)


def craft(identity: Identity, kind: str, body: dict, **overrides) -> str:
    """Build a signed envelope, optionally with tampered fields."""
    envelope = {
        "v": 1, "kind": kind, "peer": identity.peer_id,
        "pub": identity.public_hex, "ts": 1_700_000_000.0, "body": body,
    }
    envelope.update(overrides)
    envelope["sig"] = identity.sign(canonical(envelope))
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"))


@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography not installed")
class TestHappyPath(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = InMemoryBus()
        self.poster = make_node(self.bus)
        self.worker = make_node(self.bus)

    def test_full_lifecycle_converges_on_both_ledgers(self) -> None:
        task_id = self.poster.post_task("summarise", {"doc": "a"}, budget=3)
        self.assertEqual(self.worker.ledger.get(task_id).state, OPEN)

        self.worker.claim(task_id)
        self.assertIn(self.worker.peer_id, self.poster.ledger.get(task_id).claims)

        self.poster.award(task_id, self.worker.peer_id)
        self.assertEqual(self.worker.ledger.get(task_id).state, AWARDED)

        self.worker.complete(task_id, "the summary")
        self.assertEqual(self.poster.ledger.get(task_id).state, COMPLETE)

        self.poster.rate(task_id, 9, "good")
        for node in (self.poster, self.worker):
            task = node.ledger.get(task_id)
            self.assertEqual(task.state, RATED)
            self.assertEqual(task.rating, 9)
        self.assertEqual(self.poster.rejected, [])
        self.assertEqual(self.worker.rejected, [])

    def test_callbacks_fire_for_counterparties(self) -> None:
        seen: list[str] = []
        self.worker.on_task = lambda task: seen.append("task")
        self.worker.on_award = lambda task: seen.append("award")
        task_id = self.poster.post_task("summarise")
        self.worker.claim(task_id)
        self.poster.award(task_id, self.worker.peer_id)
        self.assertEqual(seen, ["task", "award"])


@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography not installed")
class TestAuthorisation(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = InMemoryBus()
        self.poster = make_node(self.bus)
        self.worker = make_node(self.bus)
        self.outsider = make_node(self.bus)
        self.task_id = self.poster.post_task("summarise", {"doc": "a"})
        self.worker.claim(self.task_id)

    def _reject_reason(self, raw: str) -> str:
        before = len(self.poster.rejected)
        self.poster._receive("spoofed-sender", raw)
        self.assertGreater(len(self.poster.rejected), before, "message was accepted")
        return self.poster.rejected[-1]

    def test_outsider_cannot_award(self) -> None:
        raw = craft(self.outsider.identity, "task.award",
                    {"task_id": self.task_id, "agent": self.outsider.peer_id})
        self.assertIn("only the poster may award", self._reject_reason(raw))
        self.assertEqual(self.poster.ledger.get(self.task_id).state, OPEN)

    def test_cannot_award_to_an_agent_that_did_not_claim(self) -> None:
        raw = craft(self.poster.identity, "task.award",
                    {"task_id": self.task_id, "agent": self.outsider.peer_id})
        self.assertIn("did not claim", self._reject_reason(raw))

    def test_outsider_cannot_complete_an_awarded_task(self) -> None:
        self.poster.award(self.task_id, self.worker.peer_id)
        raw = craft(self.outsider.identity, "task.done",
                    {"task_id": self.task_id, "result_hash": "0" * 64})
        self.assertIn("only the awarded agent", self._reject_reason(raw))

    def test_worker_cannot_rate_its_own_work(self) -> None:
        self.poster.award(self.task_id, self.worker.peer_id)
        self.worker.complete(self.task_id, "done")
        raw = craft(self.worker.identity, "task.rate",
                    {"task_id": self.task_id, "score": 10, "reason": "great"})
        self.assertIn("only the poster may rate", self._reject_reason(raw))

    def test_poster_cannot_claim_its_own_task(self) -> None:
        raw = craft(self.poster.identity, "task.claim",
                    {"task_id": self.task_id, "caps": []})
        self.assertIn("cannot claim its own", self._reject_reason(raw))


@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography not installed")
class TestIntegrity(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = InMemoryBus()
        self.poster = make_node(self.bus)
        self.attacker = make_node(self.bus)

    def _reject_reason(self, raw: str) -> str:
        before = len(self.poster.rejected)
        self.poster._receive("spoofed-sender", raw)
        self.assertGreater(len(self.poster.rejected), before, "message was accepted")
        return self.poster.rejected[-1]

    def test_task_id_must_match_contents(self) -> None:
        raw = craft(self.attacker.identity, "task.post", {
            "task_id": "deadbeefdeadbeef", "nonce": "00",
            "need": "summarise", "spec": {}, "budget": 1,
        })
        self.assertIn("does not match its contents", self._reject_reason(raw))

    def test_spec_cannot_be_altered_after_posting(self) -> None:
        """Changing the spec changes the id, so the tampered post is rejected."""
        nonce = "abc123"
        original = compute_task_id(self.attacker.peer_id, nonce, "summarise", {"pay": 10})
        raw = craft(self.attacker.identity, "task.post", {
            "task_id": original, "nonce": nonce,
            "need": "summarise", "spec": {"pay": 1}, "budget": 1,
        })
        self.assertIn("does not match its contents", self._reject_reason(raw))

    def test_unsigned_message_is_rejected(self) -> None:
        envelope = {
            "v": 1, "kind": "task.post", "peer": self.attacker.peer_id,
            "pub": self.attacker.identity.public_hex, "ts": 1.0,
            "body": {"task_id": "x", "nonce": "n", "need": "a", "spec": {}, "budget": 1},
            "sig": None,
        }
        reason = self._reject_reason(json.dumps(envelope))
        self.assertIn("signature", reason)

    def test_tampered_body_fails_signature(self) -> None:
        raw = craft(self.attacker.identity, "task.post", {
            "task_id": "x", "nonce": "n", "need": "a", "spec": {}, "budget": 1})
        envelope = json.loads(raw)
        envelope["body"]["budget"] = 9999
        self.assertIn("signature", self._reject_reason(json.dumps(envelope)))

    def test_peer_id_must_match_public_key(self) -> None:
        victim = make_node(self.bus)
        raw = craft(self.attacker.identity, "task.post", {
            "task_id": "x", "nonce": "n", "need": "a", "spec": {}, "budget": 1},
            peer=victim.peer_id)
        self.assertIn("does not match its public key", self._reject_reason(raw))

    def test_transport_sender_is_not_trusted(self) -> None:
        """A valid signature is accepted no matter what the pipe claims."""
        nonce = "n1"
        task_id = compute_task_id(self.attacker.peer_id, nonce, "summarise", {})
        raw = craft(self.attacker.identity, "task.post", {
            "task_id": task_id, "nonce": nonce,
            "need": "summarise", "spec": {}, "budget": 1})
        self.poster._receive("a-completely-different-name", raw)
        self.assertIsNotNone(self.poster.ledger.get(task_id))

    def test_malformed_input_does_not_raise(self) -> None:
        for junk in ("", "not json", "[]", "null", '{"v":1}', '{"v":99,"kind":"x"}'):
            self.poster._receive("x", junk)
        self.assertIsNotNone(self.poster.rejected)


@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography not installed")
class TestStateMachine(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = InMemoryBus()
        self.poster = make_node(self.bus)
        self.worker = make_node(self.bus)
        self.task_id = self.poster.post_task("summarise")

    def _reject_reason(self, raw: str) -> str:
        before = len(self.poster.rejected)
        self.poster._receive("x", raw)
        self.assertGreater(len(self.poster.rejected), before, "message was accepted")
        return self.poster.rejected[-1]

    def test_cannot_complete_before_award(self) -> None:
        self.worker.claim(self.task_id)
        raw = craft(self.worker.identity, "task.done",
                    {"task_id": self.task_id, "result_hash": "0" * 64})
        self.assertIn("state open", self._reject_reason(raw))

    def test_cannot_rate_before_completion(self) -> None:
        self.worker.claim(self.task_id)
        self.poster.award(self.task_id, self.worker.peer_id)
        raw = craft(self.poster.identity, "task.rate",
                    {"task_id": self.task_id, "score": 9})
        self.assertIn("state awarded", self._reject_reason(raw))

    def test_cannot_claim_after_award(self) -> None:
        self.worker.claim(self.task_id)
        self.poster.award(self.task_id, self.worker.peer_id)
        late = make_node(self.bus)
        raw = craft(late.identity, "task.claim", {"task_id": self.task_id, "caps": []})
        self.assertIn("state awarded", self._reject_reason(raw))

    def test_rating_out_of_range_rejected(self) -> None:
        self.worker.claim(self.task_id)
        self.poster.award(self.task_id, self.worker.peer_id)
        self.worker.complete(self.task_id, "x")
        raw = craft(self.poster.identity, "task.rate",
                    {"task_id": self.task_id, "score": 99})
        self.assertIn("out of range", self._reject_reason(raw))

    def test_duplicate_task_rejected(self) -> None:
        task = self.poster.ledger.get(self.task_id)
        raw = craft(self.poster.identity, "task.post", {
            "task_id": self.task_id, "nonce": "whatever",
            "need": task.need, "spec": task.spec, "budget": task.budget})
        self.assertIn("does not match its contents", self._reject_reason(raw))

    def test_message_for_unknown_task_rejected(self) -> None:
        raw = craft(self.worker.identity, "task.claim",
                    {"task_id": "0123456789abcdef", "caps": []})
        self.assertIn("unknown task", self._reject_reason(raw))


@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography not installed")
class TestLedgerToCorpus(unittest.TestCase):
    def test_rated_tasks_become_scored_work_and_endorsement_edges(self) -> None:
        from attentiophages.metrics import agent_quality, amplification_edges

        bus = InMemoryBus()
        poster, worker = make_node(bus), make_node(bus)
        for i in range(3):
            task_id = poster.post_task("summarise", {"doc": str(i)})
            worker.claim(task_id)
            poster.award(task_id, worker.peer_id)
            worker.complete(task_id, f"result {i}")
            poster.rate(task_id, 8, "fine")

        corpus = poster.ledger.to_corpus()
        self.assertEqual(len(corpus), 6)  # one work record + one rating per task

        quality = agent_quality(corpus)
        self.assertIn(worker.peer_id, quality)
        self.assertNotIn(poster.peer_id, quality)  # ratings carry no score of their own

        edges = amplification_edges(corpus)
        self.assertEqual(edges[(poster.peer_id, worker.peer_id)], 3.0)

    def test_unrated_tasks_are_excluded(self) -> None:
        bus = InMemoryBus()
        poster, worker = make_node(bus), make_node(bus)
        task_id = poster.post_task("summarise")
        worker.claim(task_id)
        poster.award(task_id, worker.peer_id)
        worker.complete(task_id, "result")
        self.assertEqual(len(poster.ledger.to_corpus()), 0)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography not installed")
class TestDelegation(unittest.TestCase):
    """A subtask may carry the principal's signed award of its parent. Or not."""

    def setUp(self) -> None:
        self.bus = InMemoryBus()
        self.client, self.hub, self.worker, self.stranger = (make_node(self.bus) for _ in range(4))
        self.parent = self.client.post_task("report", {"topic": "x"})
        self.hub.claim(self.parent)
        self.client.award(self.parent, self.hub.peer_id)

    def _reject_reason(self, node: TaskMarket, raw: str) -> str:
        before = len(node.rejected)
        node._receive("spoofed", raw)
        self.assertGreater(len(node.rejected), before, "message was accepted")
        return node.rejected[-1]

    def _post_with(self, identity: Identity, award_raw: str, parent: str | None = None) -> str:
        nonce = "00"
        need, spec = "summarise", {"s": 1}
        task_id = compute_task_id(identity.peer_id, nonce, need, spec)
        return craft(identity, "task.post", {
            "task_id": task_id, "nonce": nonce, "need": need, "spec": spec, "budget": 1,
            "delegation": {"parent": parent or self.parent, "award": award_raw},
        })

    def test_genuine_delegation_records_parent_and_principal_everywhere(self) -> None:
        sub = self.hub.post_task("summarise", {"s": 1}, delegated_from=self.parent)
        for node in (self.client, self.worker, self.stranger):
            task = node.ledger.get(sub)
            self.assertEqual(task.parent, self.parent)
            self.assertEqual(task.principal, self.client.peer_id)
        self.assertEqual([t.need for t in self.worker.ledger.chain(sub)], ["summarise", "report"])

    def test_chain_root_survives_two_levels(self) -> None:
        sub = self.hub.post_task("summarise", {"s": 1}, delegated_from=self.parent)
        self.worker.claim(sub)
        self.hub.award(sub, self.worker.peer_id)
        subsub = self.worker.post_task("fetch", {"u": 1}, delegated_from=sub)
        self.assertEqual(self.stranger.ledger.get(subsub).principal, self.client.peer_id)

    def test_cannot_delegate_from_a_task_not_awarded_to_you(self) -> None:
        with self.assertRaises(ProtocolError):
            self.stranger.post_task("x", delegated_from=self.parent)

    def test_forged_award_is_rejected(self) -> None:
        # The stranger signs an AWARD as if it were the client.
        forged = craft(self.stranger.identity, "task.award",
                       {"task_id": self.parent, "agent": self.stranger.peer_id},
                       peer=self.client.peer_id, pub=self.client.identity.public_hex)
        raw = self._post_with(self.stranger.identity, forged)
        self.assertIn("does not verify", self._reject_reason(self.worker, raw))
        self.assertNotIn(compute_task_id(self.stranger.peer_id, "00", "summarise", {"s": 1}),
                         self.worker.ledger.tasks)

    def test_real_award_reused_by_a_different_poster_is_rejected(self) -> None:
        raw = self._post_with(self.stranger.identity, self.hub.awards[self.parent])
        self.assertIn("names a different agent", self._reject_reason(self.worker, raw))

    def test_award_for_a_different_task_is_rejected(self) -> None:
        other = self.client.post_task("report", {"topic": "y"})
        self.hub.claim(other)
        self.client.award(other, self.hub.peer_id)
        raw = self._post_with(self.hub.identity, self.hub.awards[other])   # parent says x, award says y
        self.assertIn("different task", self._reject_reason(self.worker, raw))

    def test_award_from_someone_other_than_the_parents_poster_is_rejected(self) -> None:
        # A second key of the stranger's "awards" the client's task to the stranger.
        sybil = make_node(self.bus)
        fake = craft(sybil.identity, "task.award", {"task_id": self.parent, "agent": self.stranger.peer_id})
        raw = self._post_with(self.stranger.identity, fake)
        self.assertIn("not signed by the parent's poster", self._reject_reason(self.worker, raw))

    def test_late_joiner_accepts_and_names_the_signer_as_principal(self) -> None:
        late = make_node(InMemoryBus())     # never saw the parent task
        sub_raw = self._post_with(self.hub.identity, self.hub.awards[self.parent])
        late._receive("x", sub_raw)
        self.assertEqual(late.rejected, [])
        task = late.ledger.get(compute_task_id(self.hub.peer_id, "00", "summarise", {"s": 1}))
        self.assertEqual(task.principal, self.client.peer_id)

    def test_malformed_delegation_is_rejected(self) -> None:
        raw = craft(self.hub.identity, "task.post", {
            "task_id": compute_task_id(self.hub.peer_id, "01", "summarise", {}), "nonce": "01",
            "need": "summarise", "spec": {}, "budget": 1, "delegation": "yes",
        })
        self.assertIn("malformed delegation", self._reject_reason(self.worker, raw))
