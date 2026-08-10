"""Swappable transports for agent coordination.

The protocol layer (`swarm.taskmarket`) does not care how bytes move. Keeping
that boundary explicit is deliberate: a rendezvous channel is a commodity, and
the one you start on is rarely the one you finish on. Public IRC has no funding
step and no announced end-of-life but no persistence and no ordering; a chain has
both of those but costs a funding step and, in Sepolia's case, has a shutdown
date. See `docs/06-coordination.md` for measured numbers on both.

A transport is a dumb pipe. It moves strings and reports who they came from.
**It is not a trust boundary** — the sender identity a transport reports is
whatever the underlying network claims, so `taskmarket` verifies signatures
itself and ignores the transport's opinion of who sent something.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

Handler = Callable[[str, str], None]  # (claimed_sender, raw_message)


class Transport(ABC):
    """Moves opaque strings between peers."""

    @abstractmethod
    def broadcast(self, message: str) -> None:
        """Send to everyone in the rendezvous."""

    @abstractmethod
    def send(self, peer: str, message: str) -> None:
        """Send to one peer, addressed by whatever name this transport uses."""

    @abstractmethod
    def subscribe(self, handler: Handler) -> None:
        """Register a callback for inbound messages."""


class InMemoryBus:
    """A process-local stand-in for a rendezvous channel.

    Used by the tests and by `taskmarket.demo()`. Delivery is synchronous and
    ordered, which real transports are not -- see the note in
    `docs/06-coordination.md` about what that hides.
    """

    def __init__(self) -> None:
        self._members: dict[str, Handler] = {}

    def join(self, peer: str, handler: Handler) -> None:
        self._members[peer] = handler

    def leave(self, peer: str) -> None:
        self._members.pop(peer, None)

    def broadcast(self, sender: str, message: str) -> None:
        for peer, handler in list(self._members.items()):
            if peer != sender:
                handler(sender, message)

    def send(self, sender: str, target: str, message: str) -> None:
        handler = self._members.get(target)
        if handler is not None:
            handler(sender, message)


class InMemoryTransport(Transport):
    def __init__(self, bus: InMemoryBus, peer: str) -> None:
        self.bus = bus
        self.peer = peer
        self._handler: Handler | None = None

    def broadcast(self, message: str) -> None:
        self.bus.broadcast(self.peer, message)

    def send(self, peer: str, message: str) -> None:
        self.bus.send(self.peer, peer, message)

    def subscribe(self, handler: Handler) -> None:
        self._handler = handler
        self.bus.join(self.peer, handler)


class IRCTransport(Transport):
    """Carries protocol messages over an `IRCRendezvous` connection.

    Reuses the rendezvous chunking, so messages larger than an IRC line are split
    and reassembled. Note that this double-signs: the rendezvous envelope is
    signed, and the protocol message inside it is signed again. That is
    redundant but harmless, and it keeps the protocol verifiable if you swap the
    transport for one that does not sign at all.
    """

    KEY = "tm"

    def __init__(self, node) -> None:
        self.node = node
        self._handler: Handler | None = None

    def broadcast(self, message: str) -> None:
        # A channel is just another PRIVMSG target.
        self.node.send_payload(self.node.channel, {self.KEY: message})

    def send(self, peer: str, message: str) -> None:
        self.node.send_payload(peer, {self.KEY: message})

    def subscribe(self, handler: Handler) -> None:
        self._handler = handler

        def on_payload(sender_peer, body: dict) -> None:
            raw = body.get(self.KEY)
            if isinstance(raw, str):
                handler(sender_peer.peer_id, raw)

        self.node.on_payload = on_payload
