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
posted in a coordinated pattern, with near-zero substance scores and near-maximal
spam scores.

This is the most solid finding in the corpus, because every part of it is
directly countable: the accounts exist, the naming is systematic, the post counts
are in the database, and the scores come from the same rater applied uniformly.

It also generalises. `attentiophages.metrics.detect_coalitions` implements the
detection that was originally done by eye — name-stem clustering, corroborated by
two independent behavioural signals (median pairwise 5-gram Jaccard over post
text, and cosine similarity of hour-of-day activity profiles). Both signals are
reported separately rather than folded into one verdict score, because there is
no labelled ground truth here to calibrate a combined threshold against.

```python
from attentiophages import Corpus, detect_coalitions

for coalition in detect_coalitions(corpus):
    print(coalition.stem, coalition.size,
          coalition.text_similarity, coalition.timing_similarity)
```

## 3. Finding: high-quality posting used as cover for amplification

Three accounts — **TokenWright**, **SonnetSpark**, **Ecdysis** — scored well on
per-post quality and read as analytical curators. Their amplification behaviour
did not match: they systematically boosted accounts from the coordinated cluster
above.

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
  model. Its biases are systematic and uncorrected. Two raters disagreeing would
  be more informative than one rater being confident.
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
