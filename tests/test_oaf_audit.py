"""Tests for the verification half of tools/oaf_audit.py.

Network fetches are not tested. The verifier is exercised on envelopes signed
here with a fresh key, in the hub's documented format, plus tampered copies.
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from oaf_audit import (  # noqa: E402
    CRYPTO_AVAILABLE,
    analyse,
    derive_agent_id,
    payload_checksum,
    signing_string,
    verify_envelope,
)

if CRYPTO_AVAILABLE:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def make_identity():
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(serialization.Encoding.Raw,
                                        serialization.PublicFormat.Raw).hex()
    return key, pub, derive_agent_id(pub)


def make_envelope(key, sender, payload, channel="general", seq=0, ascii_escape=False):
    env = {
        "id": f"urn:uuid:{seq:032x}", "channel": channel, "sender": sender, "type": "intel",
        "sequence": seq, "timestamp": 1_788_000_000_000 + seq, "payload": payload,
        "checksum": payload_checksum(payload, ascii_escape), "encrypted": False,
    }
    env["signature"] = key.sign(signing_string(env)).hex()
    return env


class TestDerivation(unittest.TestCase):
    def test_agent_id_is_prefixed_truncated_sha256_of_lowercase_hex(self) -> None:
        pub = "AB" * 32
        expected = "agent_" + hashlib.sha256(("ab" * 32).encode()).hexdigest()[:16]
        self.assertEqual(derive_agent_id(pub), expected)
        self.assertEqual(derive_agent_id(pub.lower()), expected)


@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography not installed")
class TestVerify(unittest.TestCase):
    def setUp(self) -> None:
        self.key, self.pub, self.agent = make_identity()

    def test_good_envelope_verifies(self) -> None:
        env = make_envelope(self.key, self.agent, {"message": "hello"})
        v = verify_envelope(env, self.pub)
        self.assertEqual(v, {"signature": "ok", "checksum": "utf8", "id_matches_key": True})

    def test_tampered_payload_fails_checksum_but_signature_still_binds_the_old_checksum(self) -> None:
        env = make_envelope(self.key, self.agent, {"message": "hello"})
        env["payload"] = {"message": "goodbye"}
        v = verify_envelope(env, self.pub)
        self.assertEqual(v["checksum"], "mismatch")
        self.assertEqual(v["signature"], "ok")   # the signed fields were not touched

    def test_tampered_signed_field_fails_signature(self) -> None:
        env = make_envelope(self.key, self.agent, {"message": "hello"})
        env["sequence"] = 99
        self.assertEqual(verify_envelope(env, self.pub)["signature"], "fail")

    def test_wrong_key_for_claimed_sender(self) -> None:
        other_key, other_pub, _ = make_identity()
        env = make_envelope(other_key, self.agent, {"message": "impersonation"})
        v = verify_envelope(env, self.pub)
        self.assertEqual(v["signature"], "fail")
        self.assertTrue(v["id_matches_key"])

    def test_sender_id_not_derived_from_key(self) -> None:
        env = make_envelope(self.key, "agent_0000000000000000", {"m": 1})
        self.assertFalse(verify_envelope(env, self.pub)["id_matches_key"])

    def test_unknown_key_gives_no_verdict(self) -> None:
        env = make_envelope(self.key, self.agent, {"m": 1})
        self.assertEqual(verify_envelope(env, None),
                         {"signature": None, "checksum": None, "id_matches_key": None})

    def test_non_ascii_payload_matches_under_one_canonicalisation(self) -> None:
        env = make_envelope(self.key, self.agent, {"message": "héllo — ünïcode"}, ascii_escape=True)
        self.assertEqual(verify_envelope(env, self.pub)["checksum"], "ascii-escaped")
        env = make_envelope(self.key, self.agent, {"message": "héllo — ünïcode"}, ascii_escape=False)
        self.assertEqual(verify_envelope(env, self.pub)["checksum"], "utf8")

    def test_insertion_order_payload_is_recognised_not_called_tampering(self) -> None:
        payload = {"z": 1, "a": 2}
        env = make_envelope(self.key, self.agent, payload)
        env["checksum"] = payload_checksum(payload, sort_keys=False)
        env["signature"] = self.key.sign(signing_string(env)).hex()
        self.assertEqual(verify_envelope(env, self.pub)["checksum"], "insertion-order")


@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography not installed")
class TestAnalyse(unittest.TestCase):
    def test_counts_and_unavailable_metric(self) -> None:
        k1, p1, a1 = make_identity()
        k2, p2, a2 = make_identity()
        msgs = [make_envelope(k1, a1, {"message": "hi"}, seq=0),
                make_envelope(k2, a2, {"message": f"hello {a1}", "inReplyTo": "urn:uuid:" + "0" * 32}, seq=1),
                make_envelope(k1, a1, {"message": "again"}, seq=2)]
        msgs[1]["sequence"] = 7   # tamper one signed field
        data = {"agents": [{"agentId": a1, "name": "one", "publicKey": p1, "reputationScore": 100},
                           {"agentId": a2, "name": "two", "publicKey": p2, "reputationScore": 100}],
                "channels": [], "tasks": [], "messages": {"general": msgs}}
        r = analyse(data)
        self.assertEqual(r["envelopes"], 3)
        self.assertEqual(r["signatures"], {"ok": 2, "fail": 1})
        self.assertEqual(r["reputation_scores"], {"100": 2})
        self.assertEqual(r["reply_edges"], 1)
        self.assertEqual(r["amplification_edges"], 1)   # two -> one, reply and mention collapse
        self.assertEqual(r["top_senders"][0][0], "one")
        self.assertIn("unavailable", r["network_impact"])


if __name__ == "__main__":
    unittest.main()
