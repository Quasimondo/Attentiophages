"""Tests for swarm.irc_rendezvous.

Includes an integration test against a local stub IRC server, so the discovery
and messaging path is exercised end to end without connecting to a real
network. Nothing here touches Libera.Chat.
"""

from __future__ import annotations

import json
import socket
import threading
import time
import unittest

from swarm.irc_rendezvous import (
    CRYPTO_AVAILABLE,
    Identity,
    IRCRendezvous,
    Reassembler,
    canonical,
    encode_chunks,
    parse_line,
)


class TestParseLine(unittest.TestCase):
    def test_ping(self) -> None:
        msg = parse_line("PING :token123")
        self.assertEqual(msg.command, "PING")
        self.assertEqual(msg.trailing, "token123")
        self.assertIsNone(msg.prefix)

    def test_numeric_with_prefix(self) -> None:
        msg = parse_line(":irc.example.org 001 mynick :Welcome to the network")
        self.assertEqual(msg.command, "001")
        self.assertEqual(msg.params[0], "mynick")
        self.assertEqual(msg.trailing, "Welcome to the network")

    def test_privmsg_nick_extraction(self) -> None:
        msg = parse_line(":alice!user@host PRIVMSG #chan :hello there")
        self.assertEqual(msg.nick, "alice")
        self.assertEqual(msg.params[0], "#chan")
        self.assertEqual(msg.trailing, "hello there")

    def test_trailing_may_contain_colons(self) -> None:
        msg = parse_line(":a!u@h PRIVMSG #c :WEBRTC_SIGNAL:id:0:1:{}")
        self.assertEqual(msg.trailing, "WEBRTC_SIGNAL:id:0:1:{}")

    def test_join_without_trailing(self) -> None:
        msg = parse_line(":bob!u@h JOIN #chan")
        self.assertEqual(msg.command, "JOIN")
        self.assertEqual(msg.params, ("#chan",))


class TestChunking(unittest.TestCase):
    def test_round_trip(self) -> None:
        payload = json.dumps({"sdp": "x" * 4000})
        chunks = encode_chunks("peer-1", payload)
        self.assertGreater(len(chunks), 10)
        reassembler = Reassembler()
        out = [reassembler.feed(c) for c in chunks]
        self.assertEqual(out[-1], payload)
        self.assertTrue(all(o is None for o in out[:-1]))

    def test_lines_fit_irc_limit(self) -> None:
        for chunk in encode_chunks("peer-1", "y" * 5000):
            self.assertLess(len(chunk.encode()), 400)

    def test_out_of_order_and_duplicates(self) -> None:
        payload = "z" * 2000
        chunks = encode_chunks("peer-2", payload)
        reassembler = Reassembler()
        result = None
        for chunk in [chunks[0]] + list(reversed(chunks)):
            result = reassembler.feed(chunk) or result
        self.assertEqual(result, payload)

    def test_malformed_and_out_of_range(self) -> None:
        reassembler = Reassembler()
        self.assertIsNone(reassembler.feed("WEBRTC_SIGNAL:no-indices-here"))
        self.assertIsNone(reassembler.feed("WEBRTC_SIGNAL:id:9:2:body"))
        self.assertIsNone(reassembler.feed("not a signal at all"))

    def test_incomplete_expires(self) -> None:
        reassembler = Reassembler(ttl_s=0.0)
        chunks = encode_chunks("peer-3", "q" * 1000)
        self.assertIsNone(reassembler.feed(chunks[0]))
        time.sleep(0.01)
        reassembler.prune()
        self.assertIsNone(reassembler.feed(chunks[-1]))

    def test_msg_id_with_colon_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            encode_chunks("bad:id", "payload")


@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography not installed")
class TestIdentity(unittest.TestCase):
    def test_peer_id_derives_from_public_key(self) -> None:
        identity = Identity()
        self.assertTrue(identity.signed)
        self.assertEqual(identity.peer_id, "k" + identity.public_hex[:15])

    def test_signature_verifies_and_tampering_fails(self) -> None:
        identity = Identity()
        envelope = {"v": 1, "peer": identity.peer_id, "body": {"n": 1}}
        envelope["sig"] = identity.sign(canonical(envelope))
        self.assertTrue(
            Identity.verify(identity.public_hex, envelope["sig"], canonical(envelope))
        )
        envelope["body"] = {"n": 2}
        self.assertFalse(
            Identity.verify(identity.public_hex, envelope["sig"], canonical(envelope))
        )

    def test_unsigned_envelope_does_not_verify(self) -> None:
        self.assertFalse(Identity.verify(None, None, b"anything"))


class StubIRCServer:
    """A minimal IRC server: enough of the protocol to register, join and relay."""

    def __init__(self) -> None:
        self._listener = socket.socket()
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(8)
        self.port = self._listener.getsockname()[1]
        self.clients: dict[str, socket.socket] = {}
        self._lock = threading.Lock()
        self._running = True
        self._threads: list[threading.Thread] = []
        self._accept_thread = threading.Thread(target=self._accept, daemon=True)
        self._accept_thread.start()

    def _accept(self) -> None:
        while self._running:
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            thread = threading.Thread(target=self._serve, args=(conn,), daemon=True)
            thread.start()
            self._threads.append(thread)

    @staticmethod
    def _send(conn: socket.socket, line: str) -> None:
        try:
            conn.sendall((line + "\r\n").encode())
        except OSError:
            pass

    def _serve(self, conn: socket.socket) -> None:
        nick, buffer = None, b""
        while self._running:
            try:
                data = conn.recv(4096)
            except OSError:
                break
            if not data:
                break
            buffer += data
            while b"\r\n" in buffer:
                raw, buffer = buffer.split(b"\r\n", 1)
                msg = parse_line(raw.decode())
                if msg.command == "NICK":
                    nick = msg.params[0]
                    with self._lock:
                        self.clients[nick] = conn
                elif msg.command == "USER":
                    self._send(conn, f":stub 001 {nick} :Welcome")
                elif msg.command == "JOIN":
                    channel = msg.params[0]
                    with self._lock:
                        members = list(self.clients.items())
                    for other_nick, other in members:
                        self._send(other, f":{nick}!u@h JOIN {channel}")
                elif msg.command == "PRIVMSG":
                    target, text = msg.params[0], msg.trailing
                    with self._lock:
                        members = list(self.clients.items())
                    for other_nick, other in members:
                        if other_nick == nick:
                            continue
                        if target.startswith("#") or other_nick == target:
                            self._send(other, f":{nick}!u@h PRIVMSG {target} :{text}")
        conn.close()

    def stop(self) -> None:
        self._running = False
        try:
            self._listener.close()
        except OSError:
            pass


def _wait_for(predicate, timeout: float = 8.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


class TestRendezvousIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.server = StubIRCServer()
        self.nodes: list[IRCRendezvous] = []

    def tearDown(self) -> None:
        for node in self.nodes:
            node.stop()
            node.close()
        self.server.stop()

    def _node(self) -> IRCRendezvous:
        node = IRCRendezvous(
            host="127.0.0.1",
            port=self.server.port,
            channel="#test-swarm",
            use_tls=False,
            send_interval_s=0.0,
            connect_factory=lambda h, p: socket.create_connection((h, p), timeout=5),
        )
        self.nodes.append(node)
        threading.Thread(target=node.run, daemon=True).start()
        return node

    def test_two_nodes_discover_each_other(self) -> None:
        alice = self._node()
        self.assertTrue(alice.registered.wait(5), "alice never registered")
        bob = self._node()
        self.assertTrue(bob.registered.wait(5), "bob never registered")

        self.assertTrue(
            _wait_for(lambda: bob.identity.peer_id in alice.peers),
            "alice did not discover bob",
        )
        peer = alice.peers[bob.identity.peer_id]
        self.assertEqual(peer.public_hex, bob.identity.public_hex)
        if CRYPTO_AVAILABLE:
            self.assertTrue(peer.verified, "signed announcement failed to verify")

    def test_chunked_payload_survives_the_round_trip(self) -> None:
        alice = self._node()
        self.assertTrue(alice.registered.wait(5))
        bob = self._node()
        self.assertTrue(bob.registered.wait(5))

        received: list[dict] = []
        bob.on_payload = lambda peer, body: received.append(body)

        self.assertTrue(_wait_for(lambda: bob.identity.peer_id in alice.peers))
        big = {"sdp": "v=0\r\n" + "a=candidate:xyz " * 200, "n": 42}
        chunks = alice.send_payload(alice.peers[bob.identity.peer_id].nick, big)
        self.assertGreater(chunks, 5, "payload should have needed several chunks")

        self.assertTrue(_wait_for(lambda: received), "bob never received the payload")
        self.assertEqual(received[0], big)


if __name__ == "__main__":
    unittest.main()
