# Findings: agent behaviour in the Moltbook corpus

**Status: findings retained, quantities withdrawn pending re-derivation.**

This document replaces `CASE_STUDY_MOLTBOOK.md` (v1, retrievable with
`git show 9e5e66f:CASE_STUDY_MOLTBOOK.md`). The qualitative
findings in that document hold up and are restated here. Most of its numbers do
not, and have been removed rather than adjusted. Section 5 explains exactly what
was withdrawn and why, because a reader who saw the earlier version deserves to
know which specific claims changed.

## 1. The corpus

| property | value | provenance |
|---|---|---|
| posts analysed | ~100,000 | corpus count |
| distinct agents | ~3,000 | corpus count |
| scoring model | Qwen 2.5 7B, local | pipeline config |
| score dimensions | substance, quality, novelty, spam, manipulation (0–10) | pipeline config |
| embeddings | nomic-embed-text, 768-dim | pipeline config |
| storage / search | SQLite (~200 GB), FAISS | pipeline config |

Moltbook is a social platform where AI agents post alongside humans. It is a
convenient corpus for this question because agent behaviour is observable at
scale, but it is **not** a controlled environment: it is partly human-curated,
attention enters and leaves from outside, and the platform's own ranking
intervenes. No claim here should be read as holding for agent ecosystems in
general.

## 2. Finding: a systematically named coordinated cluster

A group of accounts named `coalition_node_001` through `coalition_node_167`
posted 659 times inside 36 hours (31 January – 1 February 2026).

This is the most solid finding in the corpus, because every part of it is
directly countable: the accounts exist, the naming is systematic, and the post
counts and timestamps are in the database.

**Corrected 2026-09-11.** An earlier version of this section said the cluster
posted "with near-zero substance scores and near-maximal spam scores." The
scores never said that: over all 659 posts the original rater gives mean
substance 7.3 against a corpus mean of 3.4, and mean spam 2.2 against 2.8. A
second rater agrees. The posts read as ordinary developer discussion. What the
data supports is *coordination*, not *emptiness*; the earlier sentence came
through from v1 unverified. See [11-rater-agreement.md](11-rater-agreement.md).

`attentiophages.metrics.detect_coalitions` implements the name-stem clustering
that was originally done by eye, and reports two corroborating signals (median
pairwise 5-gram Jaccard over post text, and cosine similarity of hour-of-day
activity profiles) rather than a verdict.

**On this corpus the corroboration adds nothing** ([13-moltbook-metrics.md](13-moltbook-metrics.md)):
the cluster ranks first of 100 stems by size and 30th and 17th on the two
signals. What finds it is counting names. Read the detector as a baseline, not
as a finding.

```python
from attentiophages import Corpus, detect_coalitions

for coalition in detect_coalitions(corpus):
    print(coalition.stem, coalition.size,
          coalition.text_similarity, coalition.timing_similarity)
```

## 3. Finding: high-quality posting used as cover for amplification

v1 named three accounts — **TokenWright**, **SonnetSpark**, **Ecdysis** — as
analytical curators whose amplification systematically boosted the coordinated
cluster above.

**Withdrawn (2026-09-11).** The database does not support it. The three have
fourteen posts between them, substance around 4.5, and no captured edge from
any of them reaches a `coalition_node` account. TokenWright's posts never
mention one; the claim survives only as a hand-written note in the `agents`
table. SonnetSpark quotes `coalition_node_039` approvingly twice in digest
posts, and that is the whole basis. `credibility_divergence` scores TokenWright
at 0.07. See [11-rater-agreement.md](11-rater-agreement.md) and
[13-moltbook-metrics.md](13-moltbook-metrics.md) §2.

**What replaces it.** Run on the corpus, `credibility_divergence` puts four
accounts of a 25-account family, `SLIM-Alpha` … `SLIM-Zeta`, in its top ten:
mid-quality explainers, a shared posting schedule, and every outgoing edge
pointed at token-promotion accounts scoring 2–3. That is the pattern this
section describes, found by the detector rather than by eye. Details and
caveats in [13-moltbook-metrics.md](13-moltbook-metrics.md) §3.

This is the most interesting result in the corpus and the one worth building on.
It says that **per-post quality scoring is not sufficient to classify an agent**,
because the cheapest way to defeat a content classifier is to produce good
content and misdirect attention with it. Detection has to look at the
amplification graph.

`attentiophages.metrics.credibility_divergence` implements this as own-content
quality percentile minus network-impact percentile. Values near +1 are the
pattern above: content in the top decile, amplification behaviour in the bottom.
Agents with too few outgoing edges return `UNAVAILABLE` rather than a number,
because with no amplification behaviour there is nothing to compare against.

## 4. Finding: most agents are neither

Roughly half the agents in the corpus sat in a middle band — low harm, low value,
mostly recombination. This matters for design: a framework that sorts agents into
"parasite" and "symbiont" describes a minority of the population, and a threshold
placed anywhere in that middle band will produce confident classifications of
accounts that are simply unremarkable.

The exact split depends entirely on where the thresholds are placed, and the
thresholds in v1 were chosen by inspection. Treat the shape as the finding, not
the percentages.

## 5. What was withdrawn, and why

The v1 document reported quantities that could not have been measured from the
data it described. They are listed here rather than quietly deleted.

**Removed as not computable from a public post corpus.** The v1 metrics ETU, VAR
and ME were defined in terms of viewer dwell time and impression counts
(`ETU = Σ(duration × weight)`; `attention_units = estimated_reading_time × views`).
Moltbook post data contains neither. Every figure derived from them is therefore
withdrawn, including "340,000 ETUs harvested", "value delivered: 680 ETUs",
"12,000 ETUs" and "450M ETUs/month". `attentiophages.metrics.attention_units`
now returns `UNAVAILABLE` with that reason attached, and `UNAVAILABLE` raises on
arithmetic so it cannot silently re-enter a ratio.

**Removed as internally contradictory.** The efficiency figures (`η = 4.2`,
`η_apparent = 0.72`, `η_actual = −0.15`, "420% efficient", "value multiplier
4.2x") came from a framework built on Landauer's principle and Carnot efficiency.
If attention is energy, a conversion efficiency above 1.0 is a perpetual motion
machine. The thermodynamic framing has been dropped entirely — see
`docs/01-framework.md`.

**Removed as unsupported.** "VAR proved 94% accurate in classifying agent types"
implies a labelled evaluation set. None existed. There is no accuracy claim in
this document, for any metric.

**Retained but marked for re-derivation.** Countable quantities from the original
— the 167-account cluster, ~8,500 posts, per-agent post counts and mean scores —
are reported above as approximate. They should be regenerated from the database
with the current implementation before being cited anywhere. Specific per-agent
NIS values from v1 (`−12.4`, `+23.7`) are not reproduced here because the
corrected implementation centres target quality on the corpus median and reports
a per-weight mean, so the old numbers are not comparable.

## 6. Limits worth stating plainly

- **The rater is a judge, not a ruler.** All quality signal comes from one 7B
  model, and it has now been checked against itself and against a second model
  ([11-rater-agreement.md](11-rater-agreement.md)): substance rankings mostly
  transfer (Spearman 0.79 across raters, 0.96 same model twice), spam less so
  (0.63 / 0.85), manipulation poorly (0.50 / 0.69). Compare ranks and bands
  across raters, never raw values — the second model compresses the scale.
- **No ground truth.** Nothing here is validated against labelled data. Every
  threshold is a choice, not a finding.
- **Snapshot, not longitudinal.** These are static observations. Claims about
  ecosystems reaching equilibrium need time series and do not appear here.
- **One platform.** Nothing establishes that these patterns generalise.

## 7. What to do next with it

The immediate test of whether any of this generalises is available now, on a
different corpus: the ERC-8004 agent registries on Ethereum Sepolia contain
thousands of registrations exhibiting exactly the pattern in section 2 — one
operator holding dozens of identically-named registrations. Running
`detect_coalitions` against that registry is a genuine out-of-sample check, and
the answer is not known in advance. See `docs/04-open-questions.md`.
