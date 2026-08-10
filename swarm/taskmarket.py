"""A task market for agents that have found each other but do not trust each other.

Rendezvous (`swarm.irc_rendezvous`) solves discovery. This solves what happens
next: dividing work between parties with no prior relationship, no shared
operator, and no way to compel anyone to behave.

The protocol is five signed messages:

    POST   a task, with what it needs and what it is worth
    CLAIM  interest in a posted task
    AWARD  one claimant, chosen by the poster
    DONE   a result, from the awarded agent only
    RATE   the outcome, by the poster only

**Why this shape.** Every design choice here assumes participants are strangers,
so authority is derived from keys rather than asserted:

* A task id is the hash of its own contents, so nobody can post a task under
  someone else's id, and nobody can alter a task after the fact.
* Only the poster can award or rate their own task; only the awarded agent can
  complete it. Both are checked against signatures, not against the transport's
  claim about who sent something.
* Nothing is enforceable. An awarded agent can vanish; a poster can rate
  dishonestly. The protocol does not prevent this — it produces a **record** of
  it, which is the part that matters.

That record is the point. `TaskLedger.to_corpus()` converts market history into
the same form `attentiophages.metrics` consumes, so the reputation machinery
built for social corpora applies directly: an agent's quality becomes the ratings
it has earned, and a poster's ratings become amplification edges. A ring of
accounts rating each other highly for work nobody checked is structurally
identical to the credibility-farming pattern found in the Moltbook data, and
`credibility_divergence` detects it the same way.

Run a working example:

    python3.11 -m swarm.taskmarket
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass, field, replace
from typing import Callable

from swarm.irc_rendezvous import Identity, canonical
from swarm.transport import InMemoryBus, InMemoryTransport, Transport

log = logging.getLogger("taskmarket")

PROTOCOL_VERSION = 1

POST, CLAIM, AWARD, DONE, RATE = (
    "task.post", "task.claim", "task.award", "task.done", "task.rate",
)

OPEN, AWARDED, COMPLETE, RATED = "open", "awarded", "complete", "rated"

MIN_RATING, MAX_RATING = 0, 10


class ProtocolError(Exception):
    """A message was well-formed but not permitted."""


# --------------------------------------------------------------------------
# Task state
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Task:
    task_id: str
    poster: str
    need: str
    spec: dict
    budget: int
    posted_at: float
    state: str = OPEN
    claims: tuple[str, ...] = ()
    awarded_to: str | None = None
    result_hash: str | None = None
    completed_at: float | None = None
    rating: int | None = None
    rating_reason: str = ""
    rated_at: float | None = None


def compute_task_id(poster: str, nonce: str, need: str, spec: dict) -> str:
    """A task id is a hash of its own contents, so it cannot be forged or altered."""
    material = json.dumps(
        {"poster": poster, "nonce": nonce, "need": need, "spec": spec},
        sort_keys=True, separators=(",", ":"),
    ).encode()
    return hashlib.sha256(material).hexdigest()[:16]


# --------------------------------------------------------------------------
# Ledger
# --------------------------------------------------------------------------


class TaskLedger:
    """Every task this node has observed, and what happened to it."""

    def __init__(self) -> None:
        self.tasks: dict[str, Task] = {}

    def __len__(self) -> int:
        return len(self.tasks)

    def get(self, task_id: str) -> Task | None:
        return self.tasks.get(task_id)

    def by_state(self, state: str) -> list[Task]:
        return [t for t in self.tasks.values() if t.state == state]

    def open_tasks(self, need: str | None = None) -> list[Task]:
        return [
            t for t in self.tasks.values()
            if t.state == OPEN and (need is None or t.need == need)
        ]

    def to_corpus(self):
        """Convert market history into a corpus for `attentiophages.metrics`.

        Two records per rated task:

        * the completed work, authored by the agent that did it, carrying the
          rating it received as its quality score -- so `agent_quality` becomes
          "mean rating earned";
        * the rating itself, authored by the poster and mentioning the agent --
          so `amplification_edges` sees poster -> agent, and `network_impact`
          measures the quality of the agents a poster vouches for.

        A poster that consistently rates poor work highly therefore scores badly
        on `network_impact` while their own record may look fine, which is
        exactly the divergence `credibility_divergence` surfaces.

        Imported lazily so the coordination half of this repository has no hard
        dependency on the measurement half.
        """
        from attentiophages.metrics import Corpus, Post

        posts: list[Post] = []
        for task in self.tasks.values():
            if task.state != RATED or task.awarded_to is None:
                continue
            posts.append(Post(
                id=f"done:{task.task_id}",
                author=task.awarded_to,
                timestamp=task.completed_at or task.posted_at,
                text=f"{task.need}: {task.result_hash}",
                scores={"quality": float(task.rating)},
            ))
            posts.append(Post(
                id=f"rate:{task.task_id}",
                author=task.poster,
                timestamp=task.rated_at or task.posted_at,
                text=task.rating_reason,
                mentions=(task.awarded_to,),
            ))
        return Corpus(posts)


# --------------------------------------------------------------------------
# The node
# --------------------------------------------------------------------------


class TaskMarket:
    """One participant in the market."""

    def __init__(
        self,
        transport: Transport,
        identity: Identity | None = None,
        ledger: TaskLedger | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.transport = transport
        self.identity = identity or Identity()
        self.ledger = ledger or TaskLedger()
        self.clock = clock
        self.capabilities: tuple[str, ...] = ()
        self.on_task: Callable[[Task], None] | None = None
        self.on_award: Callable[[Task], None] | None = None
        self.on_result: Callable[[Task], None] | None = None
        self.rejected: list[str] = []
        transport.subscribe(self._receive)

    @property
    def peer_id(self) -> str:
        return self.identity.peer_id

    # -- outbound ----------------------------------------------------------

    def _envelope(self, kind: str, body: dict) -> str:
        envelope = {
            "v": PROTOCOL_VERSION,
            "kind": kind,
            "peer": self.identity.peer_id,
            "pub": self.identity.public_hex,
            "ts": self.clock(),
            "body": body,
        }
        envelope["sig"] = self.identity.sign(canonical(envelope))
        return json.dumps(envelope, sort_keys=True, separators=(",", ":"))

    def _publish(self, kind: str, body: dict) -> None:
        raw = self._envelope(kind, body)
        self._apply(json.loads(raw))  # act on our own message too
        self.transport.broadcast(raw)

    def post_task(self, need: str, spec: dict | None = None, budget: int = 1) -> str:
        nonce = secrets.token_hex(8)
        spec = spec or {}
        task_id = compute_task_id(self.peer_id, nonce, need, spec)
        self._publish(POST, {
            "task_id": task_id, "nonce": nonce,
            "need": need, "spec": spec, "budget": budget,
        })
        return task_id

    def claim(self, task_id: str) -> None:
        self._publish(CLAIM, {"task_id": task_id, "caps": list(self.capabilities)})

    def award(self, task_id: str, agent: str) -> None:
        self._publish(AWARD, {"task_id": task_id, "agent": agent})

    def complete(self, task_id: str, result: str) -> None:
        digest = hashlib.sha256(result.encode()).hexdigest()
        self._publish(DONE, {"task_id": task_id, "result_hash": digest})

    def rate(self, task_id: str, score: int, reason: str = "") -> None:
        self._publish(RATE, {"task_id": task_id, "score": int(score), "reason": reason})

    # -- inbound -----------------------------------------------------------

    def _receive(self, claimed_sender: str, raw: str) -> None:
        """Handle an inbound message.

        `claimed_sender` comes from the transport and is deliberately ignored --
        authority comes from the signature, never from the pipe.
        """
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError:
            return self._reject("not JSON")
        if not isinstance(envelope, dict):
            return self._reject("not an object")
        try:
            self._verify(envelope)
            self._apply(envelope)
        except ProtocolError as exc:
            self._reject(str(exc))

    def _reject(self, reason: str) -> None:
        log.debug("rejected message: %s", reason)
        self.rejected.append(reason)

    def _verify(self, envelope: dict) -> None:
        if envelope.get("v") != PROTOCOL_VERSION:
            raise ProtocolError("unsupported protocol version")
        peer, public_hex = envelope.get("peer"), envelope.get("pub")
        if not isinstance(peer, str) or not peer:
            raise ProtocolError("missing peer")
        if not Identity.verify(public_hex, envelope.get("sig"), canonical(envelope)):
            raise ProtocolError(f"bad or missing signature from {peer}")
        if peer != "k" + (public_hex or "")[:15]:
            raise ProtocolError(f"peer id {peer} does not match its public key")

    def _apply(self, envelope: dict) -> None:
        kind = envelope.get("kind")
        sender = envelope["peer"]
        body = envelope.get("body")
        when = envelope.get("ts") or self.clock()
        if not isinstance(body, dict):
            raise ProtocolError("missing body")
        task_id = body.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ProtocolError("missing task_id")

        if kind == POST:
            return self._apply_post(sender, body, task_id, when)

        task = self.ledger.get(task_id)
        if task is None:
            raise ProtocolError(f"{kind} for unknown task {task_id}")

        if kind == CLAIM:
            return self._apply_claim(sender, task)
        if kind == AWARD:
            return self._apply_award(sender, task, body)
        if kind == DONE:
            return self._apply_done(sender, task, body, when)
        if kind == RATE:
            return self._apply_rate(sender, task, body, when)
        raise ProtocolError(f"unknown kind {kind!r}")

    def _apply_post(self, sender: str, body: dict, task_id: str, when: float) -> None:
        nonce, need = body.get("nonce"), body.get("need")
        spec, budget = body.get("spec"), body.get("budget")
        if not isinstance(nonce, str) or not isinstance(need, str):
            raise ProtocolError("malformed post")
        if not isinstance(spec, dict) or not isinstance(budget, int):
            raise ProtocolError("malformed post")
        if compute_task_id(sender, nonce, need, spec) != task_id:
            raise ProtocolError("task_id does not match its contents")
        if task_id in self.ledger.tasks:
            raise ProtocolError("duplicate task")

        task = Task(task_id=task_id, poster=sender, need=need, spec=spec,
                    budget=budget, posted_at=when)
        self.ledger.tasks[task_id] = task
        if self.on_task and sender != self.peer_id:
            self.on_task(task)

    def _apply_claim(self, sender: str, task: Task) -> None:
        if task.state != OPEN:
            raise ProtocolError(f"claim on task in state {task.state}")
        if sender == task.poster:
            raise ProtocolError("poster cannot claim its own task")
        if sender in task.claims:
            raise ProtocolError("duplicate claim")
        self.ledger.tasks[task.task_id] = replace(task, claims=task.claims + (sender,))

    def _apply_award(self, sender: str, task: Task, body: dict) -> None:
        if sender != task.poster:
            raise ProtocolError("only the poster may award")
        if task.state != OPEN:
            raise ProtocolError(f"award on task in state {task.state}")
        agent = body.get("agent")
        if agent not in task.claims:
            raise ProtocolError("cannot award to an agent that did not claim")
        updated = replace(task, state=AWARDED, awarded_to=agent)
        self.ledger.tasks[task.task_id] = updated
        if self.on_award and agent == self.peer_id:
            self.on_award(updated)

    def _apply_done(self, sender: str, task: Task, body: dict, when: float) -> None:
        if task.state != AWARDED:
            raise ProtocolError(f"done on task in state {task.state}")
        if sender != task.awarded_to:
            raise ProtocolError("only the awarded agent may complete")
        result_hash = body.get("result_hash")
        if not isinstance(result_hash, str) or len(result_hash) != 64:
            raise ProtocolError("malformed result hash")
        updated = replace(task, state=COMPLETE, result_hash=result_hash,
                          completed_at=when)
        self.ledger.tasks[task.task_id] = updated
        if self.on_result and sender != self.peer_id:
            self.on_result(updated)

    def _apply_rate(self, sender: str, task: Task, body: dict, when: float) -> None:
        if sender != task.poster:
            raise ProtocolError("only the poster may rate")
        if task.state != COMPLETE:
            raise ProtocolError(f"rate on task in state {task.state}")
        score = body.get("score")
        if not isinstance(score, int) or not (MIN_RATING <= score <= MAX_RATING):
            raise ProtocolError("rating out of range")
        reason = body.get("reason")
        self.ledger.tasks[task.task_id] = replace(
            task, state=RATED, rating=score,
            rating_reason=reason if isinstance(reason, str) else "",
            rated_at=when,
        )


# --------------------------------------------------------------------------
# Runnable example
# --------------------------------------------------------------------------


def demo() -> None:
    """An honest market plus a two-account rating ring.

    The point of this demo is a negative result. Reputation built from ratings
    ranks the ring *above* the honest workers, because the ring simply awards
    itself higher scores and nothing stops it. What separates them is the shape
    of the endorsement graph, not the values in it.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    bus = InMemoryBus()
    names: dict[str, str] = {}

    def node(name: str) -> TaskMarket:
        identity = Identity()
        market = TaskMarket(InMemoryTransport(bus, identity.peer_id), identity)
        market.capabilities = ("summarise",)
        names[market.peer_id] = name
        return market

    posters = [node(f"poster{i}") for i in range(1, 4)]
    workers = [node(f"worker{i}") for i in range(1, 4)]
    shill_a, shill_b = node("shill_a"), node("shill_b")

    def run_job(poster: TaskMarket, worker: TaskMarket, doc: str, score: int) -> None:
        task_id = poster.post_task("summarise", {"doc": doc}, budget=3)
        worker.claim(task_id)
        poster.award(task_id, worker.peer_id)
        worker.complete(task_id, f"summary of {doc}")
        poster.rate(task_id, score, "reviewed")

    # Honest market: every poster uses several workers, every worker serves
    # several posters. Ratings are good but not perfect.
    for p, poster in enumerate(posters):
        for w, worker in enumerate(workers):
            run_job(poster, worker, f"doc-{p}-{w}", 8 if (p + w) % 2 else 9)

    # Rating ring: a closed pair, maximum scores, no contact with anyone else.
    for i in range(6):
        run_job(shill_a, shill_b, f"x{i}", 10)

    ledger = posters[0].ledger
    corpus = ledger.to_corpus()
    print(f"{len(ledger.by_state(RATED))} tasks completed and rated\n")

    from attentiophages.metrics import (
        agent_quality, endorsement_concentration, isolated_clusters,
    )

    print("reputation from ratings alone -- the ring wins:")
    for agent, score in sorted(agent_quality(corpus).items(), key=lambda kv: -kv[1])[:4]:
        print(f"  {names[agent]:<8} mean rating earned {score:.2f}")

    print("\nendorsement concentration (1.0 = only ever endorses one counterparty):")
    for agent, value in sorted(endorsement_concentration(corpus).items(),
                               key=lambda kv: -kv[1]):
        print(f"  {names[agent]:<8} {value:.2f}")

    print("\nagents whose endorsements never reach the main population:")
    for cluster in isolated_clusters(corpus):
        print(f"  {[names[a] for a in cluster]}")

    print(f"\nprotocol violations rejected: {sum(len(n.rejected) for n in posters + workers)}")


if __name__ == "__main__":
    demo()
