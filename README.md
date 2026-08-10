# Attentiophagēs

**Telling apart agents that feed an information ecosystem from agents that drain
it — using only observable behaviour.**

Attention is the finite resource that agents in a shared information space
compete for. Some return more than they take; most return roughly nothing; a few
extract while looking like they contribute. This repository is about measuring
which is which, and it is deliberately narrow: no claims about intelligence,
alignment or intent, only about what the record shows.

```bash
git clone https://github.com/Quasimondo/Attentiophages
cd Attentiophages
python3.11 -m unittest discover -t . -s tests   # 36 tests, no dependencies
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

## What is here

| path | what it is |
|---|---|
| `attentiophages/metrics.py` | the metrics: quality, amplification graph, network impact, credibility divergence, coalition detection |
| `tests/` | 36 tests, standard library only |
| `swarm/irc_rendezvous.py` | agent rendezvous over public IRC — Ed25519 identity, chunked messaging, runs today |
| `POC_swarm/` | the original browser WebRTC demo, repaired; see its README for what still blocks it |
| `docs/` | framework, metrics reference, findings, open questions, history |

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

1. **Run the coalition detector on a second corpus.** `docs/04-open-questions.md`
   §1 sets up a concrete out-of-sample test against the ERC-8004 registries on
   Sepolia, which contain 9,514 registrations from 851 owners and visibly exhibit
   the same clustering pattern. A negative result is a real result.
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
