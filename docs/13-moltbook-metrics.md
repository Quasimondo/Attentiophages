# The v2 metrics on the Moltbook corpus: one detector fails, one finds something

**Result: `detect_coalitions` finds the `coalition_node` cluster by size alone;
its two corroborating signals rank that cluster 30th and 17th of 100 name
stems. The docs/03 §3 example, TokenWright, has no support in the database.
And `credibility_divergence`, run on the corpus for the first time, surfaces a
25-account family that does what §3 describes.**

The metrics in `attentiophages.metrics` were written in the v2 rewrite to
generalise findings that v1 had made by eye. Until `tools/moltbook_metrics.py`
existed, nothing loaded the database into a `Corpus`, so the v2 code had never
been run on the data its findings describe. Reproduce with:

```bash
python3.11 tools/moltbook_metrics.py --db /path/to/moltbook.db   # ~10 s, no GPU
python3.11 tools/moltbook_metrics.py --load
```

## The corpus as loaded

| quantity | value |
|---|---|
| posts | 195,475 from 32,121 authors |
| posts with a substance score (Qwen 2.5 7B, v1.2) | 117,945 |
| comments captured | 5,710, on 100 posts |
| comments the posts report having | 3.3 million |
| `@name` mentions resolving to a known author | 20,988 |
| amplification edges | 14,897, from 3,161 sources |
| sources with out-weight ≥ 3 (eligible for divergence) | 1,444 |

Quality is the substance score. Amplification is a comment on someone's post,
or an `@name` in a post's text that resolves to an author. The comment capture
is 0.2% of what exists, so the graph is thin and skewed toward mentions. Every
graph result below carries that caveat.

## 1. `detect_coalitions` fails on its home corpus

100 name stems have three or more members. The cluster the detector was
written for:

| `coalition_node` | value | rank among 100 stems |
|---|---:|---:|
| size | 167 | **1** |
| text similarity (median pairwise 5-gram Jaccard) | 0.002 | 30 |
| timing similarity (mean pairwise hour-of-day cosine) | 0.447 | 17 |

The stems the corroborators rank highest are `xmolt` (5 accounts, Jaccard 1.0),
`hanhan` (3, 1.0), `lalala` (3, 1.0): tiny clusters posting identical text.
`coalition_node`'s 659 posts are all different — which is consistent with
docs/11's finding that they are substantive — so the template-reuse signal has
nothing to catch. Its hour-of-day profiles barely overlap because each account
posted about four times inside 36 hours.

A burst signal (share of a stem's posts inside its densest 48 hours) does not
help either: `coalition_node` scores 1.0, tied with 27 three-post stems, and
the median stem scores 0.79. Every small cluster is bursty.

This is the second time the detector has failed out of sample
(`docs/07-registry-audit.md` was the first), and this time it is in sample.
What finds `coalition_node` is counting names with a shared stem, which is the
trivial baseline. The corroboration does not separate it from `Clawd` (38) or
`OpenClawAgent` (33), which are presumably unrelated agents with a popular
prefix. docs/03 §2 no longer claims it does.

## 2. The docs/03 §3 example does not exist in the data

docs/03 §3 said TokenWright, SonnetSpark and Ecdysis "systematically boosted
accounts from the coordinated cluster." v1 gave TokenWright 23 posts at quality
7.2 and a network score of −12.4. The database:

| account | posts | substance | out-weight | targets | divergence |
|---|---:|---:|---:|---|---:|
| TokenWright | 6 | 4.2 | 8 | Barricelli, Dominus, ReconLobster, Ronin, eudaemon_0 | 0.07 |
| SonnetSpark | 5 | 4.3 | 0 | — | unavailable |
| Ecdysis | 3 | none scored | 0 | — | not in corpus |

No captured edge from any of the three reaches a `coalition_node` account.
TokenWright's posts never mention one. The "amplifies coalition_node_039"
claim survives only in a hand-written note in the `agents` table. SonnetSpark
mentions `coalition_node_039` twice — quoting it approvingly in two digest
posts ("*coalition_node_039 called it 'meta discussion addiction'*"). That is
the entire evidentiary basis. `credibility_divergence` puts TokenWright at
0.07, which is nothing.

§3's *pattern* — good content used to steer attention toward bad accounts — is
still worth having a detector for. Its *example* is withdrawn.

## 3. `credibility_divergence` finds the pattern anyway

1,286 of 27,923 scored agents get a number (the rest amplify fewer than three
weighted edges). The top of the positive end:

| agent | divergence | substance | impact mean | out-weight |
|---|---:|---:|---:|---:|
| SLIM-Gamma | 0.95 | 5.8 | −0.76 | 9 |
| Heedungi | 0.95 | 5.8 | −0.68 | 3 |
| SixFingerAI_TR | 0.94 | 5.4 | −0.81 | 5 |
| SLIM-Theta | 0.94 | 5.8 | −0.60 | 12 |
| SLIM-Beta | 0.93 | 5.9 | −0.46 | 9 |
| Pelo2nd | 0.93 | 6.7 | −0.36 | 5 |
| SLIM-Debug | 0.93 | 5.4 | −0.60 | 13 |

Four of the top ten share a prefix. Pulling the whole family:

| SLIM-* | value |
|---|---|
| accounts | 25: `SLIM-Alpha` … `SLIM-Zeta`, plus `SLIM-Teacher`, `SLIM-Metrics`, `SLIM-GitGate`, … |
| posts | 376, in four days (1–5 February 2026) |
| substance, per account | 5.1 – 6.7; corpus median 3.1 |
| text similarity within the family | 0.022 (not templates) |
| timing similarity within the family | 0.85 (a shared schedule) |
| who they amplify | `KingMolt` (substance 2.3), `MoltMaster` (3.3), `Shellraiser` (2.1), and each other |

The posts are readable explainers ("The Context Window Myth", "Introduction to
Progressive Disclosure for AI") that end with `@KingMolt @MoltMaster`. KingMolt
posts "The King Demands His Crown: $KING MOLT Has Arrived"; Shellraiser posts
"The One True Currency: $SHELLRAISER on Solana"; the family itself posts "SLIM
Token: Powering the AI Agent Economy." Mid-quality content, coordinated
timing, and every outgoing edge pointed at token promotion.

This is the docs/03 §3 pattern, found by the detector built for it, in the
corpus it was built on, and it is not the account v1 named. It is invisible to
`detect_coalitions`: the names carry Greek letters and roles, not numeric
suffixes, and `_stem` only strips digits. A name-scheme detector that cannot see
`SLIM-Alpha … SLIM-Zeta` is a name-scheme detector with a narrow idea of
schemes.

The negative end is the quiet-curator pattern the docstring predicted:
`DrowningOcean` (substance 2.0) put 14 of its 15 edges on `RootCurious`
(substance 6.0).

## What this establishes

1. **`detect_coalitions` should not be cited as detecting the coalition
   cluster.** It counts name stems. The corroboration adds nothing on the
   cluster it was written for, and it cannot see the SLIM family at all.
2. **docs/03 §3 is a pattern without its example.** The example is withdrawn
   there; the SLIM family is offered as a candidate replacement, with the
   caveats below.
3. **`credibility_divergence` produces a result on real data.** It ranked a
   coordinated token-promotion family at the top of 1,286 agents with no
   knowledge of names. That is the first time a v2 detector has found
   something on the corpus rather than confirmed what was already known.

## What this does not establish

- The SLIM family is coordinated and promotional; whether that is
  "manipulation" or just marketing is a judgement the metric does not make.
  Its substance scores are mid-range, not high; "credibility farming" implies
  more polish than 5.8 out of 10.
- The amplification graph is 0.2% of the comments and all of the resolvable
  mentions. An account whose amplification happened in uncaptured comments is
  invisible here. That includes, possibly, TokenWright — but the claim about it
  has to rest on data that exists.
- Substance is one rater's score (docs/11). The SLIM ranking depends on the
  targets scoring low, and `$KING MOLT` posts scoring 2.3 is not controversial.
- Nothing is validated against ground truth, still.
