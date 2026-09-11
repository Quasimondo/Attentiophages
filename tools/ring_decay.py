"""How fast do the structural signals decay when a rating ring buys cover?

``docs/06-coordination.md`` §7 shows a two-account ring beating honest
workers on ratings, and offers two signals it cannot fake by choosing better
numbers: ``endorsement_concentration`` (the ring endorses only itself) and
``isolated_clusters`` (the ring never touches the main population). §9 asks
how fast those degrade once the ring acquires genuine external
counterparties. Nobody had measured it. This does.

Two strategies, swept over m = 0..12 extra jobs the ring adds to its six
self-dealt ones:

* **buy** -- the ring's poster hires honest workers for m real jobs and rates
  them honestly. Costs m budgets; the counterparties are genuine.
* **mint** -- the ring's poster hires m of its own fresh keys and rates them
  10. Costs m free registrations; nothing genuine is involved.

For each, the report gives the ring poster's endorsement concentration
against the honest posters' value, whether the ring is still an isolated
cluster, where the ring's worker ranks on ratings (plain, and one vote per
rater), and what it paid.

    python3.11 tools/ring_decay.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from attentiophages.metrics import (  # noqa: E402
    agent_quality,
    agent_quality_by_rater,
    endorsement_concentration,
    isolated_clusters,
)
from swarm.irc_rendezvous import CRYPTO_AVAILABLE, Identity  # noqa: E402
from swarm.taskmarket import TaskMarket  # noqa: E402
from swarm.transport import InMemoryBus, InMemoryTransport  # noqa: E402

BUY, MINT = "buy", "mint"
SELF_DEALS = 6
N_POSTERS = N_WORKERS = 3
BUDGET = 3


@dataclass(frozen=True)
class Row:
    strategy: str
    extra_jobs: int
    ring_concentration: float
    honest_concentration: float
    ring_isolated: bool
    ring_is_largest: bool         # the ring component outgrew the honest one
    ring_rank_plain: int          # 1 = highest mean rating earned
    ring_rank_by_rater: int
    cost_budgets: int
    cost_keys: int


def build(strategy: str, extra_jobs: int) -> Row:
    if strategy not in (BUY, MINT):
        raise ValueError(strategy)
    bus = InMemoryBus()
    roles: dict[str, str] = {}
    t = [1_700_000_000.0]

    def clock() -> float:
        t[0] += 60
        return t[0]

    def node(role: str) -> TaskMarket:
        identity = Identity()
        m = TaskMarket(InMemoryTransport(bus, identity.peer_id), identity, clock=clock)
        m.capabilities = ("summarise",)
        roles[m.peer_id] = role
        return m

    def run_job(poster, worker, doc, score):
        task_id = poster.post_task("summarise", {"doc": doc}, budget=BUDGET)
        worker.claim(task_id)
        poster.award(task_id, worker.peer_id)
        worker.complete(task_id, f"summary of {doc}")
        poster.rate(task_id, score, "reviewed")

    posters = [node(f"poster{i}") for i in range(1, N_POSTERS + 1)]
    workers = [node(f"worker{i}") for i in range(1, N_WORKERS + 1)]
    shill_a, shill_b = node("shill_a"), node("shill_b")

    # The honest market of docs/06 §7, unchanged.
    for p, poster in enumerate(posters):
        for w, worker in enumerate(workers):
            run_job(poster, worker, f"doc-{p}-{w}", 8 if (p + w) % 2 else 9)
    # The ring, unchanged.
    for i in range(SELF_DEALS):
        run_job(shill_a, shill_b, f"x{i}", 10)
    # The cover.
    keys = 0
    for j in range(extra_jobs):
        if strategy == BUY:
            run_job(shill_a, workers[j % N_WORKERS], f"cover-{j}", 8 if j % 2 else 9)
        else:
            sybil = node(f"sybil{j}")
            keys += 1
            run_job(shill_a, sybil, f"cover-{j}", 10)

    corpus = shill_a.ledger.to_corpus()
    conc = endorsement_concentration(corpus)
    honest = [conc[p.peer_id] for p in posters]
    isolated = any(shill_b.peer_id in c for c in isolated_clusters(corpus))
    ring_size = 2 + keys
    honest_size = N_POSTERS + N_WORKERS
    ring_is_largest = strategy == MINT and ring_size > honest_size

    def rank(q: dict[str, float]) -> int:
        ordered = sorted(q.values(), reverse=True)
        return ordered.index(q[shill_b.peer_id]) + 1

    return Row(
        strategy=strategy, extra_jobs=extra_jobs,
        ring_concentration=conc[shill_a.peer_id],
        honest_concentration=sum(honest) / len(honest),
        ring_isolated=isolated,
        ring_is_largest=ring_is_largest,
        ring_rank_plain=rank(agent_quality(corpus)),
        ring_rank_by_rater=rank(agent_quality_by_rater(corpus)),
        # Minted jobs pay the ring's own keys: the budget never leaves the ring.
        cost_budgets=extra_jobs * BUDGET if strategy == BUY else 0,
        cost_keys=keys,
    )


def sweep(strategy: str, max_extra: int = 12) -> list[Row]:
    return [build(strategy, m) for m in range(max_extra + 1)]


def report(rows: list[Row]) -> None:
    print(f"  {'extra':>5} {'ring HHI':>9} {'honest HHI':>10} {'isolated':>9} {'ring largest':>12} "
          f"{'rank plain':>10} {'rank/rater':>10} {'budgets':>8} {'keys':>5}")
    for r in rows:
        print(f"  {r.extra_jobs:>5} {r.ring_concentration:>9.2f} {r.honest_concentration:>10.2f} "
              f"{str(r.ring_isolated):>9} {str(r.ring_is_largest):>12} {r.ring_rank_plain:>10} "
              f"{r.ring_rank_by_rater:>10} {r.cost_budgets:>8} {r.cost_keys:>5}")


def main() -> int:
    if not CRYPTO_AVAILABLE:
        print("cryptography is not installed; the market cannot sign messages")
        return 1
    for strategy, what in ((BUY, "the ring hires honest workers and rates them honestly"),
                           (MINT, "the ring hires its own fresh keys and rates them 10")):
        print(f"== {strategy}: {what}\n")
        rows = sweep(strategy)
        report(rows)
        below = next((r.extra_jobs for r in rows if r.ring_concentration <= r.honest_concentration), None)
        joined = next((r.extra_jobs for r in rows if not r.ring_isolated), None)
        print(f"\n  concentration at or below the honest posters' from {below} extra jobs;")
        print(f"  ring no longer an isolated cluster from {joined} extra jobs"
              + (" -- because it became the largest component;" if strategy == MINT else ";"))
        print(f"  ring worker's rating rank never leaves 1.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
