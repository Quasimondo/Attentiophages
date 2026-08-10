"""Computable metrics for agent ecologies.

Design rule for this module: every quantity it returns is computable from data
that a public post corpus actually contains -- authorship, timestamps, text,
reply/mention edges, and per-post quality scores.

Quantities that require data most platforms do not expose (per-viewer dwell
time, impression counts, "attention harvested") are **not** estimated. They
return :data:`UNAVAILABLE`, which raises on arithmetic and on truth-testing so
that a missing measurement can never quietly become a plausible-looking number.

This replaces the v1 metric set (ETU / IDS / NPV / VAR / ME / EHI), which was
withdrawn because those formulas contained free weights that were never bound
and depended on view counts the source data did not have. See
``docs/05-history.md``.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import median
from typing import Iterable, Mapping, NoReturn, Sequence

__all__ = [
    "UNAVAILABLE",
    "Unavailable",
    "Post",
    "Corpus",
    "agent_quality",
    "amplification_edges",
    "NetworkImpact",
    "network_impact",
    "credibility_divergence",
    "endorsement_concentration",
    "isolated_clusters",
    "SharedIdentity",
    "shared_identity_clusters",
    "Coalition",
    "detect_coalitions",
    "attention_units",
]


# --------------------------------------------------------------------------
# Unavailability
# --------------------------------------------------------------------------


class Unavailable:
    """Marker for a quantity the source data cannot support.

    Deliberately hostile. It raises on truth-testing and on every arithmetic
    operation, so an unavailable value cannot be silently folded into a mean,
    a ratio, or a report table. If you see this propagate, the fix is to
    obtain the missing data -- not to substitute a default.
    """

    __slots__ = ("reason",)

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"UNAVAILABLE({self.reason!r})"

    def _refuse(self, *_: object) -> NoReturn:
        raise TypeError(f"quantity is unavailable: {self.reason}")

    __bool__ = _refuse
    __float__ = _refuse
    __int__ = _refuse
    __add__ = __radd__ = _refuse
    __sub__ = __rsub__ = _refuse
    __mul__ = __rmul__ = _refuse
    __truediv__ = __rtruediv__ = _refuse
    __lt__ = __le__ = __gt__ = __ge__ = _refuse


UNAVAILABLE = Unavailable("no measurement available")


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Post:
    """One post by one agent.

    ``scores`` holds per-dimension judgements on a 0-10 scale, typically from
    an LLM rater (the Moltbook study used ``substance``, ``quality``,
    ``novelty``, ``spam``, ``manipulation``). A post with no scores still
    contributes to edges and timing, just not to quality.
    """

    id: str
    author: str
    timestamp: float
    text: str = ""
    parent_id: str | None = None
    mentions: tuple[str, ...] = ()
    upvotes: int | None = None
    scores: Mapping[str, float] = field(default_factory=dict)


class Corpus:
    """An indexed collection of posts."""

    def __init__(self, posts: Iterable[Post]) -> None:
        self.posts: tuple[Post, ...] = tuple(posts)
        self._by_id: dict[str, Post] = {p.id: p for p in self.posts}
        self._by_author: dict[str, list[Post]] = defaultdict(list)
        for p in self.posts:
            self._by_author[p.author].append(p)

    def __len__(self) -> int:
        return len(self.posts)

    @property
    def authors(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_author))

    def by_author(self, author: str) -> tuple[Post, ...]:
        return tuple(self._by_author.get(author, ()))

    def parent_author(self, post: Post) -> str | None:
        """Author of the post this one replies to, if that post is in corpus."""
        if post.parent_id is None:
            return None
        parent = self._by_id.get(post.parent_id)
        return parent.author if parent else None


# --------------------------------------------------------------------------
# Quality
# --------------------------------------------------------------------------


def agent_quality(
    corpus: Corpus,
    dimension: str = "quality",
    prior_weight: float = 5.0,
) -> dict[str, float]:
    """Shrunk mean score per agent, in the units of ``dimension``.

    Each agent's mean is pulled toward the corpus mean with weight
    ``prior_weight``, expressed in posts::

        shrunk = (n * agent_mean + prior_weight * corpus_mean) / (n + prior_weight)

    Without shrinkage a single lucky post outranks a sustained record, which
    is how the v1 analysis let low-volume accounts dominate the top of the
    quality table. Agents with no scored posts are omitted from the result
    rather than defaulted, so callers must decide what to do about them.
    """
    if prior_weight < 0:
        raise ValueError("prior_weight must be non-negative")

    per_agent: dict[str, list[float]] = defaultdict(list)
    for post in corpus.posts:
        value = post.scores.get(dimension)
        if value is not None:
            per_agent[post.author].append(float(value))

    all_values = [v for values in per_agent.values() for v in values]
    if not all_values:
        return {}
    corpus_mean = sum(all_values) / len(all_values)

    return {
        author: (sum(values) + prior_weight * corpus_mean) / (len(values) + prior_weight)
        for author, values in per_agent.items()
    }


# --------------------------------------------------------------------------
# Amplification graph
# --------------------------------------------------------------------------


def amplification_edges(
    corpus: Corpus,
    reply_weight: float = 1.0,
    mention_weight: float = 1.0,
) -> dict[tuple[str, str], float]:
    """Directed amplification weights ``(src, dst) -> weight``.

    An agent amplifies another by replying to them or naming them. Self-edges
    are dropped: talking about yourself is not amplification.
    """
    edges: dict[tuple[str, str], float] = defaultdict(float)
    known = set(corpus.authors)
    for post in corpus.posts:
        parent = corpus.parent_author(post)
        if parent is not None and parent != post.author:
            edges[(post.author, parent)] += reply_weight
        for target in post.mentions:
            if target != post.author and target in known:
                edges[(post.author, target)] += mention_weight
    return dict(edges)


@dataclass(frozen=True)
class NetworkImpact:
    """Result of :func:`network_impact` for one agent.

    ``total`` is the sum of amplified agents' quality relative to the corpus
    baseline, weighted by amplification strength. Negative means the agent
    systematically boosts below-baseline accounts.

    ``mean`` is ``total / out_weight`` -- the average quality of what this
    agent amplifies. Use ``mean`` to compare agents of different volumes and
    ``total`` to rank by absolute ecosystem effect.
    """

    agent: str
    total: float
    mean: float
    out_weight: float
    targets: int


def network_impact(
    corpus: Corpus,
    dimension: str = "quality",
    prior_weight: float = 5.0,
) -> dict[str, NetworkImpact]:
    """Score each agent by the quality of the agents it amplifies.

    This is the v1 "Network Impact Score", corrected in two ways: target
    quality is centred on the corpus median before weighting (so amplifying a
    typical account scores ~0 rather than strongly positive), and a per-weight
    mean is reported alongside the total (so prolific accounts do not
    automatically outrank selective ones).

    Targets with no scored posts contribute nothing -- unknown quality is
    treated as absence of evidence, not as zero quality.
    """
    quality = agent_quality(corpus, dimension=dimension, prior_weight=prior_weight)
    if not quality:
        return {}
    baseline = median(quality.values())
    edges = amplification_edges(corpus)

    totals: dict[str, float] = defaultdict(float)
    weights: dict[str, float] = defaultdict(float)
    targets: dict[str, set[str]] = defaultdict(set)

    for (src, dst), weight in edges.items():
        if dst not in quality:
            continue
        totals[src] += weight * (quality[dst] - baseline)
        weights[src] += weight
        targets[src].add(dst)

    return {
        agent: NetworkImpact(
            agent=agent,
            total=total,
            mean=total / weights[agent] if weights[agent] else 0.0,
            out_weight=weights[agent],
            targets=len(targets[agent]),
        )
        for agent, total in totals.items()
    }


# --------------------------------------------------------------------------
# Credibility divergence
# --------------------------------------------------------------------------


def _percentiles(values: Mapping[str, float]) -> dict[str, float]:
    """Map each key to its rank percentile in [0, 1]; ties share the midpoint."""
    if not values:
        return {}
    ordered = sorted(values.items(), key=lambda kv: kv[1])
    n = len(ordered)
    if n == 1:
        return {ordered[0][0]: 0.5}

    result: dict[str, float] = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        midpoint = (i + j) / 2 / (n - 1)
        for k in range(i, j + 1):
            result[ordered[k][0]] = midpoint
        i = j + 1
    return result


def credibility_divergence(
    corpus: Corpus,
    dimension: str = "quality",
    min_out_weight: float = 3.0,
) -> dict[str, float | Unavailable]:
    """Own-content percentile minus network-impact percentile, in [-1, 1].

    This is the repository's one genuinely original detector. It targets
    "credibility farming": accounts whose own posts read as high quality while
    their amplification behaviour consistently boosts low-quality accounts.

    - Near ``+1``: content looks excellent, amplification behaviour is poor.
      This is the pattern that surfaced TokenWright in the Moltbook data.
    - Near ``0``: content and amplification agree.
    - Near ``-1``: unremarkable posts, but reliably boosts good accounts --
      the quiet-curator pattern.

    Agents amplifying less than ``min_out_weight`` get :data:`UNAVAILABLE`:
    with too few outgoing edges there is no network signal to compare against,
    and inventing one is how the v1 analysis manufactured false precision.
    """
    quality = agent_quality(corpus, dimension=dimension)
    impact = network_impact(corpus, dimension=dimension)
    if not quality:
        return {}

    eligible = {
        agent: result.mean
        for agent, result in impact.items()
        if result.out_weight >= min_out_weight and agent in quality
    }

    quality_pct = _percentiles({a: quality[a] for a in quality})
    impact_pct = _percentiles(eligible)

    out: dict[str, float | Unavailable] = {}
    for agent in quality:
        if agent in impact_pct:
            out[agent] = quality_pct[agent] - impact_pct[agent]
        else:
            out[agent] = Unavailable(
                f"{agent!r} amplifies fewer than {min_out_weight} weighted edges; "
                "no network signal to compare against own-content quality"
            )
    return out


# --------------------------------------------------------------------------
# Coalition / sybil detection
# --------------------------------------------------------------------------


_SUFFIX = re.compile(r"[\W_]*\d+\Z")


def _stem(handle: str) -> str:
    """Strip a trailing numeric suffix: ``coalition_node_042`` -> ``coalition_node``."""
    return _SUFFIX.sub("", handle)


def _shingles(text: str, k: int = 5) -> set[str]:
    tokens = re.findall(r"\w+", text.lower())
    if len(tokens) < k:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _hour_profile(posts: Sequence[Post]) -> list[float]:
    hours = [0.0] * 24
    for post in posts:
        hour = datetime.fromtimestamp(post.timestamp, tz=timezone.utc).hour
        hours[hour] += 1.0
    total = sum(hours)
    return [h / total for h in hours] if total else hours


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


@dataclass(frozen=True)
class SharedIdentity:
    """One label claimed by many independent controllers."""

    label: str
    controllers: tuple[str, ...]
    claims: int

    @property
    def controller_count(self) -> int:
        return len(self.controllers)


def shared_identity_clusters(
    claims: Iterable[tuple[str, str]],
    min_controllers: int = 3,
) -> list[SharedIdentity]:
    """Find labels claimed repeatedly from *distinct* controlling accounts.

    ``claims`` is an iterable of ``(label, controller)`` pairs -- a display name
    and whoever registered it. A label appearing under many separate controllers
    is the signature of one operator minting fresh accounts per registration,
    which is the cheapest way to defeat both of the other detectors here:

    * grouping by controller sees one registration each, so nothing stands out;
    * :func:`detect_coalitions` needs a numeric suffix to strip, and a reused
      name has none.

    This was added after :func:`detect_coalitions` failed an out-of-sample test
    against a live agent registry, where the dominant coordination pattern was
    exactly this and neither existing method saw it. See
    ``docs/07-registry-audit.md``.

    Reuse alone is not proof of a single operator -- "Payer" and "Test" are names
    two strangers might pick independently. Weight generic labels accordingly.
    """
    by_label: dict[str, list[str]] = defaultdict(list)
    for label, controller in claims:
        if isinstance(label, str) and label.strip():
            by_label[label.strip()].append(controller)

    results = [
        SharedIdentity(label=label, controllers=tuple(sorted(set(controllers))),
                       claims=len(controllers))
        for label, controllers in by_label.items()
        if len(set(controllers)) >= min_controllers
    ]
    results.sort(key=lambda s: (-s.controller_count, -s.claims, s.label))
    return results


def endorsement_concentration(corpus: Corpus) -> dict[str, float]:
    """Herfindahl index of each agent's outgoing amplification, in (0, 1].

    ``1.0`` means every endorsement an agent has ever made went to a single
    counterparty; ``1/n`` means they were spread evenly over ``n``.

    This exists because scores alone cannot detect a rating ring. Two accounts
    that only ever endorse each other can award themselves whatever ratings they
    like, and a quality metric built from those ratings will rank them at the
    top -- ``swarm/taskmarket.py``'s demo shows exactly that happening. What
    distinguishes the ring is not the value of its endorsements but their
    *shape*: total concentration on a counterparty that reciprocates.

    High concentration is suspicious, not damning. A specialist with one client
    looks identical. Read it alongside :func:`isolated_clusters`.
    """
    edges = amplification_edges(corpus)
    out_weight: dict[str, float] = defaultdict(float)
    for (src, _), weight in edges.items():
        out_weight[src] += weight

    concentration: dict[str, float] = defaultdict(float)
    for (src, _), weight in edges.items():
        share = weight / out_weight[src]
        concentration[src] += share * share
    return dict(concentration)


def isolated_clusters(corpus: Corpus) -> list[tuple[str, ...]]:
    """Groups of agents whose amplification never reaches the main population.

    Treats the amplification graph as undirected, finds its connected
    components, and returns every component except the largest, ordered by size.

    A closed rating ring is a component unto itself: its members endorse each
    other and nobody else, and nobody outside endorses them. That structure
    survives any choice of ratings, which is what makes it a better signal than
    the ratings themselves.

    Small corpora produce many small components for innocent reasons. This is a
    filter for attention, not a verdict.
    """
    edges = amplification_edges(corpus)
    neighbours: dict[str, set[str]] = defaultdict(set)
    for src, dst in edges:
        neighbours[src].add(dst)
        neighbours[dst].add(src)

    seen: set[str] = set()
    components: list[tuple[str, ...]] = []
    for start in neighbours:
        if start in seen:
            continue
        stack, group = [start], []
        seen.add(start)
        while stack:
            node = stack.pop()
            group.append(node)
            for other in neighbours[node]:
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
        components.append(tuple(sorted(group)))

    components.sort(key=len, reverse=True)
    return components[1:]


@dataclass(frozen=True)
class Coalition:
    """A suspected coordinated cluster of accounts."""

    stem: str
    members: tuple[str, ...]
    text_similarity: float
    timing_similarity: float

    @property
    def size(self) -> int:
        return len(self.members)


def detect_coalitions(
    corpus: Corpus,
    min_size: int = 3,
    max_pairs: int = 200,
) -> list[Coalition]:
    """Find clusters of accounts sharing a name stem, with corroboration.

    Naming alone is weak evidence -- ``user_1`` and ``user_2`` may be
    unrelated. So each name cluster is corroborated with two independent
    behavioural signals, both reported rather than folded into a single
    verdict score:

    - ``text_similarity``: median pairwise 5-gram Jaccard over members' posts,
      which catches template reuse.
    - ``timing_similarity``: mean pairwise cosine over hour-of-day activity
      profiles, which catches a shared scheduler.

    This generalises the ``coalition_node_001..167`` cluster found by hand in
    the Moltbook data. Interpretation is left to the caller: no threshold here
    is validated against labelled ground truth, and the repository does not
    claim one.
    """
    clusters: dict[str, list[str]] = defaultdict(list)
    for author in corpus.authors:
        stem = _stem(author)
        if stem and stem != author:
            clusters[stem].append(author)

    results: list[Coalition] = []
    for stem, members in sorted(clusters.items()):
        if len(members) < min_size:
            continue
        members = sorted(members)

        profiles = {m: _hour_profile(corpus.by_author(m)) for m in members}
        texts = {
            m: _shingles(" ".join(p.text for p in corpus.by_author(m)))
            for m in members
        }

        text_scores: list[float] = []
        time_scores: list[float] = []
        pairs = 0
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                text_scores.append(_jaccard(texts[a], texts[b]))
                time_scores.append(_cosine(profiles[a], profiles[b]))
                pairs += 1
                if pairs >= max_pairs:
                    break
            if pairs >= max_pairs:
                break

        results.append(
            Coalition(
                stem=stem,
                members=tuple(members),
                text_similarity=median(text_scores) if text_scores else 0.0,
                timing_similarity=(
                    sum(time_scores) / len(time_scores) if time_scores else 0.0
                ),
            )
        )

    results.sort(key=lambda c: (-c.size, c.stem))
    return results


# --------------------------------------------------------------------------
# Deliberately not implemented
# --------------------------------------------------------------------------


def attention_units(corpus: Corpus) -> Unavailable:
    """Attention actually captured by each agent. Not computable here.

    The v1 documents defined ``ETU = sum(duration * weight)`` and
    ``attention_units = estimated_reading_time * views``, then reported totals
    such as "340,000 ETUs harvested" and "450M ETUs/month". A public post
    corpus contains neither per-viewer dwell time nor impression counts, so
    those figures could not have been measured and were withdrawn.

    Measuring this requires platform-side telemetry. Until such data is
    attached, this returns :data:`Unavailable` rather than a proxy, because a
    proxy here silently changes every downstream ratio.
    """
    return Unavailable(
        "attention capture requires per-viewer dwell time or impression counts, "
        "which a public post corpus does not contain"
    )
