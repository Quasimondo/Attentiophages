# Attentiophagēs

**How agents find each other and divide work — and how to tell which of them are
worth working with.**

Two halves, and they need each other:

- **Coordination.** Strangers with no shared operator have to meet somewhere,
  agree who does what, and record what happened. `swarm/` has a working
  rendezvous daemon, a swappable transport layer, and a five-message task market.
- **Measurement.** Open coordination means anyone can show up. Attention is the
  finite resource they compete for: some return more than they take, most return
  roughly nothing, and a few extract while looking like they contribute.
  `attentiophages/` measures which is which.

The connection is the whole point. **Permissionless coordination is only viable
if you can tell who is worth coordinating with.** The ERC-8004 agent registry on
Sepolia holds 9,514 registrations from 851 owners. In an 800-registration sample,
678 usable records carry **39 distinct names**, and a single address accounts for
**500 of them**. That is what an open directory looks like without an immune
system — and its `ReputationRegistry` emitted 9 events in the last week.

```bash
git clone https://github.com/Quasimondo/Attentiophages
cd Attentiophages
python3.11 -m unittest discover -t . -s tests   # 70 tests, no dependencies
python3.11 -m swarm.taskmarket                  # a market, and a rating ring beating it
```

## The finding worth your time

**Per-post quality does not classify an agent.** An account can produce genuinely
good posts and still be net extractive, by spending the credibility those posts
earn on directing attention to accounts that are not.

This was observed in a corpus of ~100,000 posts from ~3,000 agents: three
accounts scoring 7–8/10 on content quality, reading as thoughtful curators,
systematically amplifying members of a 167-account coordinated cluster. Content
scoring rated them highly. Only the amplification graph exposed them.

It follows that any detector reading content alone is cheap to defeat, because
producing plausible high-quality text is now approximately free. The graph is
harder to fake, because it requires the cooperation of accounts that are
themselves visible and scoreable.

`credibility_divergence` implements this:

```python
from attentiophages import Corpus, credibility_divergence

for agent, score in credibility_divergence(corpus).items():
    print(agent, score)   # near +1: reads well, amplifies badly
```

## The negative result worth your time

Run `python3.11 -m swarm.taskmarket`. It stands up an honest market — three
posters, three workers, cross-linked, ratings of 8 and 9 — next to a two-account
ring that posts work to itself and awards itself 10s.

```
reputation from ratings alone -- the ring wins:
  shill_b  mean rating earned 9.61
  worker1  mean rating earned 8.96
  worker3  mean rating earned 8.96
  worker2  mean rating earned 8.83
```

The ring ranks **first**. That is the metric working correctly on a corpus where
the adversary controls its own scores, and it is what any reputation system built
from self-reported ratings does.

What separates them is the *shape* of the endorsement graph, not the values in
it — `endorsement_concentration` gives the ring 1.00 against the honest posters'
0.33, and `isolated_clusters` reports the pair as never touching the main
population. The general principle: **prefer signals whose cost to fake is
structural rather than numerical.** Full write-up in
[docs/06-coordination.md](docs/06-coordination.md) §7.

## What is here

| path | what it is |
|---|---|
| `swarm/irc_rendezvous.py` | rendezvous over public IRC — Ed25519 identity, chunked messaging, runs today |
| `swarm/taskmarket.py` | the task market: post, claim, award, done, rate — all signed, all adversarially tested |
| `swarm/transport.py` | swappable transports, so IRC or a chain are interchangeable |
| `attentiophages/metrics.py` | quality, amplification graph, network impact, credibility divergence, endorsement concentration, coalition detection |
| `tests/` | 70 tests, standard library only |
| `tools/erc8004_audit.py` | points the detectors at the live ERC-8004 registry on Sepolia |
| `POC_swarm/` | the original browser WebRTC demo, repaired; see its README for what still blocks it |
| `docs/` | framework, metrics, findings, coordination, registry audit, open questions, history |

## Documentation

- **[docs/01-framework.md](docs/01-framework.md)** — the ecology lens and, more
  importantly, where the metaphor stops
- **[docs/02-metrics.md](docs/02-metrics.md)** — every formula, every variable
  bound
- **[docs/03-findings-moltbook.md](docs/03-findings-moltbook.md)** — what the
  corpus showed, and which earlier claims were withdrawn
- **[docs/04-open-questions.md](docs/04-open-questions.md)** — five questions
  with methods attached, any of which could come out wrong
- **[docs/05-history.md](docs/05-history.md)** — what changed in v2 and why
- **[docs/06-coordination.md](docs/06-coordination.md)** — the long one:
  rendezvous as a Schelling point, a census of who is actually out there, and
  measured transport economics (Sepolia at 1.02 gwei, blobs at 128 KB for
  0.000008 ETH, why reads are the wall and not writes)
- **[docs/07-registry-audit.md](docs/07-registry-audit.md)** — an out-of-sample
  test the detector **failed**, and the pattern it missed

## Status, honestly

This is a research repository, and it has been substantially rewritten. The v1
theory was withdrawn: it borrowed thermodynamics without its constraints, and
reported attention-conversion efficiencies above 100%, which under its own
framing is a perpetual motion machine. The v1 metrics were unimplementable —
their formulas contained weights that were never specified. The v1 reference
implementation was 100 lines of stubs returning hardcoded numbers, and the v1
proof of concept had a syntax error that meant it had never run at all.

What survived is the ecological lens, the two findings above, and the corpus
work behind them. `docs/05-history.md` lists every withdrawn claim individually.
v1 remains in git history at commit `9e5e66f` — `git show 9e5e66f:Section2.md`
retrieves any of it.

**Not yet established:** every quality score traces to a single 7B rater, nothing
is validated against labelled ground truth, no metric here has a known accuracy,
and none of it has been tested outside one platform. Treat distributions as the
output; any threshold is a decision by whoever acts on it.

## Contributing

The most useful contributions, in order:

1. **Find a corpus where these detectors earn their keep.** The first
   out-of-sample test went badly — see
   [docs/07-registry-audit.md](docs/07-registry-audit.md) — and the trivial
   "group by controller" baseline beat `detect_coalitions` outright. A corpus
   where it wins, or a fourth signal that beats the baseline, is the most useful
   thing anyone could add.
2. **Re-rate a sample with a different model.** If a second rater disagrees, most
   of the findings are properties of Qwen 2.5 7B rather than of agent
   populations. Cheap, never done — §4.
3. **Attack `credibility_divergence`.** It assumes amplification is harder to
   fake than content. That assumption is unexamined — §3.

Please open an issue or pull request on GitHub. If you are reporting a finding,
include the command that regenerates it; the standing rule in this repository is
that a number without a way to reproduce it does not go in.

## License

MIT — see [LICENSE](LICENSE).

## Citation

```
Attentiophagēs: measuring contribution and extraction in agent ecosystems
Mario Klingemann, 2025-2026
https://github.com/Quasimondo/Attentiophages
```
