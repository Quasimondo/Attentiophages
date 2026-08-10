# Out-of-sample test: the detectors against a live agent registry

**Result: `detect_coalitions` failed. It found nothing the trivial baseline did
not.** A third pattern, invisible to both methods, turned out to dominate the
corpus.

This answers question 1 of `docs/04-open-questions.md`. Reproduce with:

```bash
python3.11 tools/erc8004_audit.py --sample 800
python3.11 tools/erc8004_audit.py --load      # re-analyse without re-fetching
```

## Method

Corpus: the 800 most recent ERC-721 mints on the ERC-8004 `IdentityRegistry`
(`0x8004A818BFB912233c491871b3d84c89A494BD9e`) on Ethereum Sepolia, blocks
11,340,718–11,458,515, collected 2026-08-10.

Of those, 769 `tokenURI`s resolved, 684 agent cards were fetched, and 678 carried
a name — **39 distinct names across 678 registrations.**

Each registration became one post: author = the card's `name`, text = its
`description`, timestamp = the real block timestamp (fetched, not interpolated;
registrations whose block timestamp could not be retrieved were dropped rather
than estimated).

The baseline to beat: group registrations by owner address, flag any owner with
three or more.

## What the baseline found

| owner | registrations | names |
|---|---:|---|
| `0x92aae08579…` | **500** | all "Trust City Exchange" |
| `0x7621630cb6…` | 46 | Census #1 … #7 |
| `0x04cf0368f7…` | 7 | Strands DEX Agent, Testing |

Three groups, 25 distinct names. One address is responsible for 500 of 678
registrations in the sample — 74% of the corpus is one operator, registering the
same name repeatedly, with `domain: example.com`.

## What the detector found

One cluster: stem `'Census'`, six members, all owned by the single address that
grouping-by-owner had already flagged.

```
detector names: 6   baseline names: 25   overlap: 6
found by detector but NOT by owner-grouping: []
```

Zero value added. Worse, its corroborating signals were weak where it did fire:
`text_similarity = 0.00` (the Census cards have genuinely different
descriptions) and `timing_similarity = 0.43`. The cluster was carried entirely by
the name stem.

**Why it failed.** `detect_coalitions` was built from one hand-found example —
`coalition_node_001…167`, a cluster whose members shared a stem, reused templates
and posted on a shared schedule. It encodes that example. A registry has no post
text to speak of, registrations are one-shot so there is no schedule to share,
and the operators here did not use numeric suffixes. A detector fitted to one
example generalised to nothing, which is the ordinary outcome and worth stating
plainly.

## What both methods missed

| name | registrations | distinct owners |
|---|---:|---:|
| Payer | 38 | **38** |
| Requestor | 32 | **32** |
| Requestor Hermes demo agent | 15 | **15** |
| Payer Hermes demo agent | 14 | **14** |
| Payer AgentCore clean-room agent | 8 | **8** |
| Requestor AgentCore clean-room agent | 8 | **8** |

One name, a fresh address for every registration. Grouping by owner sees a single
registration per address and finds nothing. Stem-matching needs a numeric suffix
and there is none. Six labels, none caught by either method.

Hence `shared_identity_clusters(claims, min_controllers=3)`, which takes
`(label, controller)` pairs and reports labels claimed from many distinct
controllers.

## What this pattern actually is — and why that matters

**These are almost certainly not adversaries.** The cards describe themselves as
*"Ephemeral Clockchain Handshake testnet identity"*. This is a test harness
minting a throwaway identity per run, exactly as designed.

That is the honest reading, and it is more useful than a Sybil accusation would
have been. The signal is structurally real — one identity, many minters, invisible
to the other two methods — but the *interpretation* is benign here. It fires on
any per-run ephemeral identity minting, adversarial or not, which means on a real
registry it is a filter for attention and never a verdict. "Payer" and "Test" are
also names two strangers might pick independently.

Correctly labelling a detector's own dominant hit as benign is the difference
between a measurement and an accusation.

## The reputation layer is not in use

The `ReputationRegistry` (`0x8004B663056A597Dffe9eCcC1965A193B7388713`) emitted
**9 events in the last 50,000 blocks** — roughly a week.

This matters for the rest of this repository. `network_impact`,
`credibility_divergence`, `endorsement_concentration` and `isolated_clusters` all
need an endorsement graph, and a registry with no feedback has no edges at all
(`isolated_clusters` returned 0, as expected). The identity layer is being used
heavily and the trust layer is not being used at all — which is precisely the
gap `swarm/taskmarket.py` exists to fill, by generating a rating record as a side
effect of work actually being done.

## Conclusions

1. **`detect_coalitions` does not generalise off its training example.** It
   should not be presented as a general Sybil detector, and `docs/02-metrics.md`
   now says so.
2. **The trivial baseline is strong.** Group by controller first; make any
   detector prove it adds something.
3. **Different systems coordinate differently.** Social corpora produce clusters
   that share text and timing; permissionless registries produce clusters that
   share nothing but a name. A method built on one will not transfer.
4. **The dominant structure in this registry is one operator with 500
   registrations.** Any statistic over ERC-8004 that does not deduplicate by
   controller is mostly measuring that one address.

## Limits

- One registry, one 800-registration sample, one day.
- Owner address is a proxy for "operator", and a weak one — the whole point of the
  third finding is that operators mint fresh addresses.
- 122 of 800 registrations yielded no usable card and were excluded. Whether
  unreachable cards correlate with the patterns above was not tested.
- No ground truth. Nothing here is validated against a labelled set, and no
  accuracy is claimed for any of the three methods.
