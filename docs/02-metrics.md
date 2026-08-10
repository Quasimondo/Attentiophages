# Metrics reference

Every metric here is implemented in `attentiophages/metrics.py` and covered by
`tests/test_metrics.py`. Every variable below is bound — if a symbol appears in a
formula, this document says where its value comes from. The v1 metric set failed
that test: `ETU`, `IDS` and `NPV` each contained weights (`w_i`, `d_i`, `c_i`,
`s_i`, `v_i`) that were never specified anywhere, which made them unimplementable.

## Input

```python
from attentiophages import Corpus, Post

corpus = Corpus([
    Post(id="p1", author="alice", timestamp=1_700_000_000.0,
         text="...", parent_id=None, mentions=("bob",),
         scores={"quality": 8.1, "spam": 0.2}),
])
```

`scores` holds per-dimension ratings on a 0–10 scale. In the Moltbook work these
came from a local Qwen 2.5 7B rater. Any rater works; the metrics do not care
where the numbers come from, only that the same rater was applied uniformly.

## `agent_quality(corpus, dimension="quality", prior_weight=5.0)`

Mean score per agent, shrunk toward the corpus mean:

```
shrunk(a) = (n_a · mean_a + w · mean_corpus) / (n_a + w)
```

- `n_a` — number of posts by agent `a` carrying `dimension`
- `mean_a` — mean of those scores
- `mean_corpus` — mean of `dimension` across every scored post
- `w` — `prior_weight`, in units of posts; default 5

Without shrinkage a single lucky post outranks a sustained record. Agents with no
scored posts are **omitted** from the result rather than defaulted, so callers
must decide explicitly what to do about them.

## `amplification_edges(corpus, reply_weight=1.0, mention_weight=1.0)`

Directed weights `(src, dst) → weight`. An agent amplifies another by replying to
them or naming them. Self-edges are excluded, and mentions of agents absent from
the corpus are ignored.

Both weights default to 1.0 because there is no principled basis for preferring
one signal over the other. If you have such a basis for your platform, pass it in
rather than hard-coding it here.

## `network_impact(corpus, dimension="quality", prior_weight=5.0)`

For each agent, the quality of what it amplifies:

```
total(a) = Σ_b  weight(a→b) · (quality(b) − median_quality)
mean(a)  = total(a) / Σ_b weight(a→b)
```

- `quality(b)` — `agent_quality` for the target
- `median_quality` — median over all agents with a quality value

Two corrections to v1's Network Impact Score:

1. **Centred on the median.** Amplifying a typical account now scores ≈ 0.
   Uncentred, every amplifier scored positive and the metric mostly measured
   volume.
2. **A per-weight mean is reported alongside the total.** Use `mean` to compare
   agents of different volumes, `total` to rank by absolute effect on the system.

Targets with no quality value contribute nothing. Unknown quality is absence of
evidence, not evidence of zero quality.

## `credibility_divergence(corpus, dimension="quality", min_out_weight=3.0)`

```
divergence(a) = percentile(quality(a)) − percentile(network_impact_mean(a))
```

Both percentiles are rank-based in `[0, 1]`, ties sharing the midpoint, so the
result lies in `[−1, 1]`.

| value | reading |
|---|---|
| near +1 | content in the top decile, amplification in the bottom — the credibility-farming pattern |
| near 0 | content and amplification agree |
| near −1 | unremarkable content, reliably amplifies good accounts |

Agents amplifying less than `min_out_weight` return `UNAVAILABLE`. With too few
outgoing edges there is no network signal, and manufacturing one is exactly how
v1 produced false precision.

**There is no threshold here.** The distribution is the output. Any cutoff is a
decision by the person acting on it, and should be recorded as such.

## `detect_coalitions(corpus, min_size=3, max_pairs=200)`

Finds accounts sharing a name stem after a trailing numeric suffix is stripped
(`coalition_node_042` → `coalition_node`), then reports two independent
corroborating signals:

- `text_similarity` — median pairwise Jaccard over 5-gram shingles of members'
  concatenated posts. Catches template reuse.
- `timing_similarity` — mean pairwise cosine over 24-bin hour-of-day activity
  profiles. Catches a shared scheduler.

They are reported separately and deliberately **not** combined into a verdict
score. Name similarity alone is weak evidence; `user_1` and `user_2` may be
strangers. There is no ground truth here to calibrate a combined threshold
against, so the caller does the judging.

`max_pairs` bounds the pairwise comparison on large clusters. When it binds, the
similarity figures are computed from a subset — relevant if you are comparing
clusters of very different sizes.

## `attention_units(corpus)` — deliberately unavailable

Returns `UNAVAILABLE`. Attention actually captured requires per-viewer dwell time
or impression counts, which a public post corpus does not contain.

`UNAVAILABLE` raises `TypeError` on arithmetic, truth-testing and comparison:

```python
>>> attention_units(corpus)
UNAVAILABLE('attention capture requires per-viewer dwell time or ...')
>>> attention_units(corpus) * 2
TypeError: quantity is unavailable: attention capture requires ...
```

This is the intended behaviour, not an inconvenience to route around. The v1
analysis substituted a plausible estimate here, and every downstream ratio
inherited it while looking measured. If you need this quantity, obtain
platform-side telemetry; do not supply a proxy.
