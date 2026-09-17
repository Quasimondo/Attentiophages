# Rater agreement: how much of docs/03 is Qwen 2.5 7B?

**Result: substance rankings mostly survive a change of rater; spam less so;
manipulation is noisy even when the same model rates the same post twice.
And the re-rating exposed a claim in docs/03 §2 that the original scores never
supported.**

This answers question 4 of `docs/04-open-questions.md`. Reproduce with:

```bash
python3 tools/rater_agreement.py --db /path/to/moltbook.db --rate   # ~1 h on one GPU
python3 tools/rater_agreement.py --report
```

## Method

877 posts from the Moltbook corpus, drawn with a fixed seed: 60 per original
substance score 0–10 (660), every post by the three curator accounts of
docs/03 §3 (7), 60 from the `coalition_node` cluster of docs/03 §2, and 150
that carry an original manipulation score, which only 4,470 posts do. Posts
over 6,000 characters were excluded.

Each post was rated again, twice, with the three prompts copied verbatim from
the pipeline that produced the original scores (prompt version v1.2), fed the
same way (title, blank line, body):

- **retest** — Qwen 2.5 7B again, the original model. This bounds how much
  agreement is possible at all: the original run sampled at default
  temperature, so a second run of the same model is the ceiling.
- **qwen3.5** — Qwen 3.5 9B (Q4_K_M, thinking off). The actual question.

Spam has 747 comparable posts and manipulation 174, because the original run
did not score every post on every dimension. No rating failed to parse.

## Agreement

Spearman rank correlation, share of exact matches, share within one point,
and share landing in the same decision band as the pipeline's own thresholds:

| substance | n | Spearman | exact | ±1 | same band |
|---|---:|---:|---:|---:|---:|
| original vs retest | 877 | **0.96** | 0.53 | 0.92 | 0.85 |
| original vs qwen3.5 | 877 | **0.79** | 0.27 | 0.65 | 0.68 |
| retest vs qwen3.5 | 877 | 0.80 | 0.26 | 0.65 | 0.69 |

| spam | n | Spearman | exact | ±1 | same band |
|---|---:|---:|---:|---:|---:|
| original vs retest | 747 | **0.85** | 0.60 | 0.78 | 0.90 |
| original vs qwen3.5 | 747 | **0.63** | 0.28 | 0.43 | 0.78 |
| retest vs qwen3.5 | 747 | 0.61 | 0.33 | 0.47 | 0.78 |

| manipulation | n | Spearman | exact | ±1 | same band |
|---|---:|---:|---:|---:|---:|
| original vs retest | 174 | **0.69** | 0.64 | 0.74 | 0.89 |
| original vs qwen3.5 | 174 | **0.50** | 0.47 | 0.65 | 0.71 |
| retest vs qwen3.5 | 174 | 0.49 | 0.46 | 0.62 | 0.73 |

Reading the gap between the first two rows of each table as "the part that is
the rater": for substance it is 0.96 → 0.79, for spam 0.85 → 0.63, for
manipulation 0.69 → 0.50. Substance is the dimension the findings lean on, and
it is the one that travels best. Manipulation does not agree with itself: the
same model, same prompt, same post lands in the same band 89% of the time and
on the same score 64% of the time.

**The second rater compresses the scale.** Mean Qwen 3.5 score per original
score:

```
original   0    1    2    3    4    5    6    7    8    9   10
retest   0.1  0.7  1.4  2.7  3.7  4.6  5.7  6.8  7.8  8.8  9.8
qwen3.5  0.9  1.7  2.4  4.3  4.7  5.0  5.7  6.1  6.8  7.9  8.4
```

Qwen 3.5 rates the original's 0s at about 1 and its 10s at about 8. Anything
that compares scores *across* raters by value is wrong; ranks and bands are
what transfer. The retest is also slightly below the diagonal everywhere: the
sample was stratified on the original score, so every re-rating regresses
toward the corpus mean, which is low (3.4). That is selection, not drift.

## What it does to docs/03

**§2, the coalition cluster.** The document said the 167 `coalition_node`
accounts posted "with near-zero substance scores and near-maximal spam scores."
The original rater never said that. Over all 659 of the cluster's posts:

| coalition_node, Qwen 2.5 v1.2 | cluster | whole corpus |
|---|---:|---:|
| mean substance | **7.3** | 3.4 |
| posts scoring substance ≥ 7 | 525 of 659 | — |
| mean spam | **2.2** | 2.8 |

Qwen 3.5 agrees (sample of 60: mean substance 6.4, spam 3.1). The posts are
titled like ordinary developer discussion — "FastAPI + SQLModel is a shipping
machine", "How do you decide when to rebuild vs iterate on existing code?".
What the data supports is coordination: 167 systematically named accounts,
659 posts inside 36 hours. What it does not support is that the content was
empty. The sentence came through the v2 rewrite from v1 unverified, in the
paragraph that called itself the most solid finding in the corpus. docs/03 §2
is corrected.

**§3, the curators.** TokenWright, SonnetSpark and Ecdysis have 7 posts
between them in the database. Their mean substance under the three raters is
4.9, 4.6 and 5.7; spam 2.3, 3.3 and 5.3. Seven posts cannot carry a claim
about "high-quality posting", and the finding's real content — that these
accounts amplified the coalition — is a graph fact, not a score. docs/03 §3
now says so.

## What this does not establish

- Two raters from one family. Qwen 3.5 is a different generation, not a
  different lineage. A rater from another family could agree less.
- One prompt. Everything here is conditional on the v1.2 rubric. A different
  rubric is a different measurement, not a check on this one.
- No ground truth. Agreement between raters says the scores are reproducible,
  not that they are right. docs/03 §6 already says this and still does.
- The manipulation sample is small (174) and the dimension is rare: the
  original mean is 1.4 on a 0–10 scale, so most of the disagreement is
  between 0, 1 and 2.
