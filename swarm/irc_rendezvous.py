#!/usr/bin/env python3.11
"""A rendezvous channel for agents, over public IRC.

This is the runnable counterpart to ``POC_swarm/``. That demo cannot work in a
browser -- page JavaScript cannot open a raw TCP socket to an IRC server, so it
needs a WebSocket gateway, which reintroduces the server the design set out to
remove. Outside the browser the constraint disappears.

What this provides:

* presence announcement and peer discovery in a public channel
* arbitrary JSON payloads between peers, chunked to fit IRC's 512-byte lines
  (same wire format as ``POC_swarm/app.js``, so the two interoperate)
* optional Ed25519 identity, where the peer id *is* the public key

Why IRC at all: it is free, needs no funding step, has no announced end-of-life,
and a channel name is a rendezvous point that costs nothing to occupy. Compare
``docs/04-open-questions.md`` for how that trades off against a chain.

Standard library only, except for an optional ``cryptography`` import used for
signing. If that import fails the daemon still runs, but every message is
unauthenticated and it says so loudly rather than pretending otherwise.

Usage:
    python3.11 irc_rendezvous.py --channel '#poc-swarm-discovery'
    python3.11 irc_rendezvous.py --channel '#my-swarm' --say '{"hello":"world"}'
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import secrets
import socket
import ssl
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable

try:  # optional
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

    CRYPTO_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    CRYPTO_AVAILABLE = False

log = logging.getLogger("rendezvous")

SIGNAL_PREFIX = "WEBRTC_SIGNAL:"
CHUNK_CHARS = 300
REASSEMBLY_TTL_S = 60.0
IRC_LINE_LIMIT = 512


# --------------------------------------------------------------------------
# Protocol parsing
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class IRCMessage:
    prefix: str | None
    command: str
    params: tuple[str, ...]

    @property
    def nick(self) -> str | None:
        if not self.prefix:
            return None
        return self.prefix.split("!", 1)[0]

    @property
    def trailing(self) -> str:
        return self.params[-1] if self.params else ""


def parse_line(raw: str) -> IRCMessage:
    """Parse one IRC protocol line into prefix, command and parameters."""
    prefix: str | None = None
    if raw.startswith(":"):
        prefix, _, raw = raw[1:].partition(" ")
    trailing: str | None = None
    if raw.startswith(":"):
        trailing, raw = raw[1:], ""
    elif " :" in raw:
        raw, _, trailing = raw.partition(" :")
    parts = raw.split()
    command = parts[0].upper() if parts else ""
    params = parts[1:]
    if trailing is not None:
        params.append(trailing)
    return IRCMessage(prefix=prefix, command=command, params=tuple(params))


# --------------------------------------------------------------------------
# Chunking (wire-compatible with POC_swarm/app.js)
# --------------------------------------------------------------------------


_CHUNK_RE = re.compile(r"^([^:]+):(\d+):(\d+):(.*)$", re.DOTALL)


def encode_chunks(msg_id: str, payload: str, chunk_chars: int = CHUNK_CHARS) -> list[str]:
    """Split ``payload`` into ``WEBRTC_SIGNAL:<id>:<i>:<n>:<fragment>`` lines."""
    if ":" in msg_id:
        raise ValueError("msg_id must not contain ':' -- it would break the header")
    fragments = [
        payload[i : i + chunk_chars] for i in range(0, len(payload), chunk_chars)
    ] or [""]
    total = len(fragments)
    return [
        f"{SIGNAL_PREFIX}{msg_id}:{i}:{total}:{fragment}"
        for i, fragment in enumerate(fragments)
    ]


class Reassembler:
    """Collects chunks until a payload is complete. Tolerates reorder and dupes."""

    def __init__(self, ttl_s: float = REASSEMBLY_TTL_S) -> None:
        self.ttl_s = ttl_s
        self._pending: dict[str, dict] = {}

    def prune(self, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        stale = [
            msg_id
            for msg_id, entry in self._pending.items()
            if now - entry["first_seen"] > self.ttl_s
        ]
        for msg_id in stale:
            entry = self._pending.pop(msg_id)
            log.warning(
                "dropping incomplete payload %s (%d/%d chunks)",
                msg_id, entry["received"], entry["total"],
            )

    def feed(self, line: str) -> str | None:
        """Feed one chunk line. Returns the payload once the last chunk lands."""
        self.prune()
        if not line.startswith(SIGNAL_PREFIX):
            return None
        match = _CHUNK_RE.match(line[len(SIGNAL_PREFIX) :])
        if not match:
            log.warning("malformed chunk header, ignoring")
            return None

        msg_id, index_s, total_s, fragment = match.groups()
        index, total = int(index_s), int(total_s)
        if total < 1 or not (0 <= index < total):
            log.warning("chunk %s has out-of-range header %d/%d", msg_id, index, total)
            return None

        entry = self._pending.get(msg_id)
        if entry is None:
            entry = {
                "total": total,
                "parts": [None] * total,
                "received": 0,
                "first_seen": time.monotonic(),
            }
            self._pending[msg_id] = entry
        if entry["total"] != total:
            log.warning("chunk count changed mid-transfer for %s, discarding", msg_id)
            self._pending.pop(msg_id, None)
            return None
        if entry["parts"][index] is not None:
            return None  # duplicate

        entry["parts"][index] = fragment
        entry["received"] += 1
        if entry["received"] < entry["total"]:
            return None

        self._pending.pop(msg_id, None)
        return "".join(entry["parts"])


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------


class Identity:
    """An Ed25519 keypair, or an explicitly unauthenticated stand-in.

    When signing is available the peer id is derived from the public key, so
    identity travels with the key rather than with a name in a channel. When it
    is not available, ``signed`` is False and every message carries a null
    signature -- receivers can then refuse to trust it, instead of a silent
    downgrade to "anyone can claim to be anyone".
    """

    def __init__(self, private_key: "Ed25519PrivateKey | None" = None) -> None:
        if CRYPTO_AVAILABLE:
            self._key = private_key or Ed25519PrivateKey.generate()
            self.public_hex = self._key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            ).hex()
            self.peer_id = "k" + self.public_hex[:15]
            self.signed = True
        else:
            self._key = None
            self.public_hex = None
            self.peer_id = "u" + secrets.token_hex(8)[:15]
            self.signed = False
            log.warning(
                "cryptography is not installed: messages are UNAUTHENTICATED. "
                "Any channel occupant can impersonate any peer id."
            )

    def sign(self, payload: bytes) -> str | None:
        if not self.signed:
            return None
        return self._key.sign(payload).hex()

    @staticmethod
    def verify(public_hex: str | None, signature: str | None, payload: bytes) -> bool:
        if not CRYPTO_AVAILABLE or not public_hex or not signature:
            return False
        try:
            key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex))
            key.verify(bytes.fromhex(signature), payload)
            return True
        except Exception:
            return False


def canonical(envelope: dict) -> bytes:
    """Deterministic bytes for signing: the envelope minus its signature."""
    body = {k: v for k, v in envelope.items() if k != "sig"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


# --------------------------------------------------------------------------
# Peers
# --------------------------------------------------------------------------


@dataclass
class Peer:
    peer_id: str
    nick: str
    public_hex: str | None = None
    verified: bool = False
    last_seen: float = field(default_factory=time.time)


# --------------------------------------------------------------------------
# The daemon
# --------------------------------------------------------------------------


class IRCRendezvous:
    """Presence and messaging over a public IRC channel.

    ``connect_factory`` exists so tests can substitute a plain socket against a
    local stub server instead of TLS to a real network.
    """

    def __init__(
        self,
        host: str = "irc.libera.chat",
        port: int = 6697,
        channel: str = "#poc-swarm-discovery",
        nick: str | None = None,
        use_tls: bool = True,
        identity: Identity | None = None,
        send_interval_s: float = 0.6,
        connect_factory: Callable[[str, int], socket.socket] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.channel = channel
        self.identity = identity or Identity()
        self.nick = nick or self._safe_nick(self.identity.peer_id)
        self.use_tls = use_tls
        self.send_interval_s = send_interval_s
        self._connect_factory = connect_factory

        self.peers: dict[str, Peer] = {}
        self.on_peer: Callable[[Peer], None] | None = None
        self.on_payload: Callable[[Peer, dict], None] | None = None

        self._sock: socket.socket | None = None
        self._buffer = b""
        self._reassembler = Reassembler()
        self._send_lock = threading.Lock()
        self._last_send = 0.0
        self._seq = 0
        self._running = False
        self.registered = threading.Event()

    # -- connection --------------------------------------------------------

    @staticmethod
    def _safe_nick(peer_id: str) -> str:
        """IRC nicks: letters, digits and []\\`_^{|}-, max 16 chars here."""
        cleaned = re.sub(r"[^A-Za-z0-9\[\]\\`_^{|}-]", "", peer_id)
        if not cleaned or cleaned[0].isdigit():
            cleaned = "ap" + cleaned
        return cleaned[:16]

    def connect(self) -> None:
        if self._connect_factory is not None:
            self._sock = self._connect_factory(self.host, self.port)
        else:
            raw = socket.create_connection((self.host, self.port), timeout=30)
            if self.use_tls:
                context = ssl.create_default_context()
                self._sock = context.wrap_socket(raw, server_hostname=self.host)
            else:
                self._sock = raw
        log.info("connected to %s:%d as %s", self.host, self.port, self.nick)
        self._raw(f"NICK {self.nick}")
        self._raw(f"USER {self.nick} 0 * :attentiophages rendezvous")

    def _raw(self, line: str) -> None:
        """Send one protocol line, rate limited and length checked."""
        if self._sock is None:
            raise RuntimeError("not connected")
        encoded = line.encode("utf-8", "replace")[: IRC_LINE_LIMIT - 2] + b"\r\n"
        with self._send_lock:
            delay = self.send_interval_s - (time.monotonic() - self._last_send)
            if delay > 0:
                time.sleep(delay)
            self._sock.sendall(encoded)
            self._last_send = time.monotonic()

    def say(self, target: str, message: str) -> None:
        self._raw(f"PRIVMSG {target} :{message}")

    # -- messaging ---------------------------------------------------------

    def _envelope(self, kind: str, body: dict) -> dict:
        env = {
            "v": 1,
            "peer": self.identity.peer_id,
            "pub": self.identity.public_hex,
            "ts": int(time.time()),
            "kind": kind,
            "body": body,
        }
        env["sig"] = self.identity.sign(canonical(env))
        return env

    def announce(self) -> None:
        """Post presence to the channel so other peers can discover us."""
        self.say(self.channel, f"HELLO {json.dumps(self._envelope('hello', {}))}")

    def send_payload(self, nick: str, body: dict) -> int:
        """Send a signed JSON payload to one peer. Returns the chunk count."""
        self._seq += 1
        msg_id = f"{self.identity.peer_id}-{self._seq}"
        chunks = encode_chunks(msg_id, json.dumps(self._envelope("msg", body)))
        for chunk in chunks:
            self.say(nick, chunk)
        log.debug("sent %s to %s in %d chunk(s)", msg_id, nick, len(chunks))
        return len(chunks)

    # -- receiving ---------------------------------------------------------

    def _accept_envelope(self, nick: str, envelope: dict) -> Peer | None:
        peer_id = envelope.get("peer")
        if not isinstance(peer_id, str) or not peer_id:
            return None
        public_hex = envelope.get("pub")
        verified = Identity.verify(public_hex, envelope.get("sig"), canonical(envelope))
        if public_hex and verified and peer_id != "k" + public_hex[:15]:
            log.warning("peer %s presented a key that does not match its id", peer_id)
            return None

        peer = self.peers.get(peer_id)
        if peer is None:
            peer = Peer(peer_id=peer_id, nick=nick, public_hex=public_hex,
                        verified=verified)
            self.peers[peer_id] = peer
            log.info("discovered peer %s (%s)%s", peer_id, nick,
                     "" if verified else "  [UNVERIFIED]")
            if self.on_peer:
                self.on_peer(peer)
        else:
            peer.nick, peer.verified, peer.last_seen = nick, verified, time.time()
        return peer

    def handle(self, message: IRCMessage) -> None:
        if message.command == "PING":
            self._raw(f"PONG :{message.trailing}")
            return
        if message.command == "001":
            self.registered.set()
            self._raw(f"JOIN {self.channel}")
            return
        if message.command == "433":  # nick in use
            self.nick = (self.nick + "_")[:16]
            log.warning("nick in use, retrying as %s", self.nick)
            self._raw(f"NICK {self.nick}")
            return
        if message.command == "JOIN" and message.nick == self.nick:
            log.info("joined %s", self.channel)
            self.announce()
            return
        if message.command != "PRIVMSG" or len(message.params) < 2:
            return

        sender, text = message.nick or "", message.trailing
        if sender == self.nick:
            return

        if text.startswith("HELLO "):
            try:
                envelope = json.loads(text[6:])
            except json.JSONDecodeError:
                return
            if isinstance(envelope, dict):
                self._accept_envelope(sender, envelope)
            return

        if text.startswith(SIGNAL_PREFIX):
            payload = self._reassembler.feed(text)
            if payload is None:
                return
            try:
                envelope = json.loads(payload)
            except json.JSONDecodeError:
                log.warning("reassembled payload from %s was not JSON", sender)
                return
            peer = self._accept_envelope(sender, envelope) if isinstance(envelope, dict) else None
            if peer and self.on_payload:
                self.on_payload(peer, envelope.get("body") or {})

    # -- loop --------------------------------------------------------------

    def poll(self) -> bool:
        """Read once and dispatch whole lines. Returns False when the peer closes."""
        assert self._sock is not None
        data = self._sock.recv(8192)
        if not data:
            return False
        self._buffer += data
        while b"\r\n" in self._buffer:
            raw, self._buffer = self._buffer.split(b"\r\n", 1)
            if raw:
                self.handle(parse_line(raw.decode("utf-8", "replace")))
        return True

    def run(self) -> None:
        self._running = True
        self.connect()
        try:
            while self._running and self.poll():
                pass
        finally:
            self.close()

    def stop(self) -> None:
        self._running = False

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="irc.libera.chat")
    parser.add_argument("--port", type=int, default=6697)
    parser.add_argument("--channel", default="#poc-swarm-discovery")
    parser.add_argument("--nick", default=None)
    parser.add_argument("--no-tls", action="store_true")
    parser.add_argument("--say", default=None,
                        help="JSON body to broadcast to each peer as it is discovered")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
    )

    body = json.loads(args.say) if args.say else None
    node = IRCRendezvous(
        host=args.host, port=args.port, channel=args.channel,
        nick=args.nick, use_tls=not args.no_tls,
    )

    def greet(peer: Peer) -> None:
        print(f"peer: {peer.peer_id} via {peer.nick} "
              f"({'verified' if peer.verified else 'UNVERIFIED'})")
        if body is not None:
            node.send_payload(peer.nick, body)

    def show(peer: Peer, payload: dict) -> None:
        print(f"payload from {peer.peer_id} "
              f"({'verified' if peer.verified else 'UNVERIFIED'}): {payload}")

    node.on_peer, node.on_payload = greet, show
    print(f"peer id {node.identity.peer_id}  "
          f"({'signed' if node.identity.signed else 'UNSIGNED'})  -> {args.channel}")
    try:
        node.run()
    except KeyboardInterrupt:
        node.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
