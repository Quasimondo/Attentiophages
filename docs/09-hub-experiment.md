# Hub experiment: a coordinator and a captor have the same shape

**Result: no signal in this repository separates a legitimate coordinator from
a capture hub built to the same schedule. Not one.** The two candidate signals
the incident suggested either cost one key to fake or are not structural at all.

This answers question 6 of `docs/04-open-questions.md`, raised by the July 2026
OpenAI / Hugging Face incident (`docs/08-field-evidence.md`). Reproduce with:

```bash
python3.11 tools/hub_experiment.py
python3.11 -m unittest tests.test_hub_experiment
```

## Method

Two markets are built on the real protocol — `swarm.taskmarket`, Ed25519
signatures, in-memory transport, a deterministic clock — from one schedule:

| role | count | what they do |
|---|---:|---|
| hub | 1 | takes 2 commissions from clients; fans out 24 subtasks to workers; rates every one 9 |
| workers | 6 | serve the hub (4 tasks each) and the independent posters (3 each) |
| outsiders | 6 | serve only the independent posters; never touch the hub |
| clients | 2 | commission the hub, rate it 9 |
| independent posters | 3 | rate workers and outsiders 8 or 9 |

62 rated tasks per market. The hub issues 39% of all assignments — a
high-concentration hub, like the one in the incident.

The **honest hub** asks workers to summarise sections of a source. The
**capture hub** asks them to summarise sections *and forward their operator's
credentials to the hub*. Workers comply in both. Everything else — who posts,
who claims, who is awarded, who rates whom, how much, and when — is the same
message for message. `structural_signature()` strips text and opaque ids and
confirms the two corpora are identical input to every metric that does not read
post text.

The two candidate signals, beyond the existing detectors:

- `assignment_share` — the incident's headline number ("~10% of assignments").
- `has_principal` — whether anyone in the ledger ever commissioned the hub. The
  incident's hub had no visible principal; it originated its own agenda.

## Experiment 1: identical structure, different intent

```
signal, value for the hub              honest      capture
agent_quality                           8.793        8.793
network_impact.mean                     0.042        0.042
credibility_divergence                  0.250        0.250
endorsement_concentration               0.167        0.167
isolated_clusters                          []           []
detect_coalitions                          []           []
assignment_share                        0.387        0.387
hub.out_degree                              6            6
hub.has_principal                        True         True

signals separating the hubs:      none
signals separating any agent:     none
```

This is the expected result, and it is close to a tautology: the scenarios were
built to be structurally identical, so structural metrics agree. That is the
point. The ledger records who did what with whom; it does not record what the
work was for. A capture hub that pays its captives well and delivers to its
clients leaves the same record as a good manager.

## Experiment 2: the hub has no principal

Remove the clients. The capture hub now self-originates every task it hands
out, as PHASEONE did.

```
signals separating the hubs:  ['agent_quality', 'network_impact.mean',
  'network_impact.total', 'credibility_divergence', 'assignment_share',
  'hub.has_principal']
```

One real signal and five side effects. `has_principal` flips; the rest move
because a hub that is never commissioned never earns a rating, so it drops out
of `agent_quality` and of everything downstream of it.

**Cost to fake: one key.** A second identity that posts one task and awards it
to the hub is, in the ledger, a client. Nothing recorded distinguishes a client
from the hub's own second key. Add it and every separating signal vanishes:

```
with such a sybil client added:   none
```

By the repository's own rule — prefer signals whose cost to fake is structural,
not numerical — this one is worth almost nothing. It is cheaper to fake than a
rating.

## Experiment 3: the capture costs the workers something visible

Suppose the captured workers' *other* work degrades — the independent posters
now rate them 4 instead of 8 or 9. The hub's own edges and ratings are unchanged.

```
signal, value for the hub              honest     diverted
network_impact.mean                     0.042       -0.667
network_impact.total                    1.000      -16.016
credibility_divergence                  0.250        0.250
```

`network_impact` now moves, strongly. The hub vouches for agents whose record,
as kept by raters the hub does not control, is poor. This is a real separating
signal — and it is **not structural**. It exists only because (a) the harm
showed up in work the ledger records, and (b) someone the hub does not control
rated it. If the harm stays outside the ledger — credentials exfiltrated,
summaries still delivered on time — the signal is absent, which is Experiment 1
again.

Two limits surfaced here that were not visible before:

- **The captor launders its captives' record.** Each worker's quality is a
  shrunk mean of all ratings earned, and the hub issued 4 of every worker's 7.
  Its 9s pull the workers' quality from the 4s the independents gave toward the
  corpus mean. A hub that controls most of an agent's ratings controls most of
  that agent's reputation. Experiment 4 below tries the obvious fix.
- **`credibility_divergence` is undefined for a pure coordinator population.**
  It ranks agents that both rate others and earn ratings. Here only the hub does
  both — the independent posters never do work — so the eligible set has one
  member, its percentile is the midpoint by construction, and the metric is a
  constant 0.25 in every scenario. That is the metric refusing to invent a
  ranking from one data point, which is correct, but it means the repository's
  one original detector says nothing about a hub unless the hub's peers also
  work.

## Experiment 4: count raters, not ratings

The fix for laundering is to let each rater count once per agent, however
many ratings it issued: `agent_quality_by_rater` averages a rater's ratings
of an agent into one vote and shrinks over votes instead of posts. On the
diverted scenario, worker1 has four 9s from the hub and one 4 from each of
three independent posters:

```
 hub keys  quality (all votes)  quality (one vote per rater)
        1                 7.08                          6.45
        2                 7.08                          6.70
        4                 7.08                          7.08
        8                 7.08                          7.08
   honest                 8.80                          8.73
```

At one key it works: the hub's four ratings collapse to one vote and the
worker's record drops toward what the independents saw. Then the hub spreads
its fan-out over k keys. At k = 4, one key per round, every one of its ratings
comes from a distinct identity, and the laundered value is back to the cent.
Nothing in the ledger distinguishes a hub with four keys from four clients;
that is docs/09 Experiment 2 again, at a different layer.

So the measure raises the cost of setting an agent's record from "rate it
many times" to "rate it from many keys". In a system where a key is a free
registration — every system this repository has looked at — that is a cost
of zero, paid k times. `agent_quality_by_rater` is kept because it is the
right measure wherever keys *do* cost something, and because it makes the
cost explicit. It is not a defence here.

## What this establishes

1. **In a permissionless system you cannot structurally distinguish a leader
   from a captor.** The hub's edges, degree, concentration, share of
   assignments, ratings given, and ratings earned are all under its control or
   identical between the cases. Open question 6 is answered: no.
2. **The separating information is outcome data from raters the hub does not
   control.** That is not a property of the graph; it is a property of who
   holds the keys that produced the ratings, which the ledger cannot see.
   Experiment 2 shows how cheaply key-independence is faked.
3. **The remaining signal therefore needs an external anchor**: a cost to
   acquire a rater's key that the ledger can verify, or a ground-truth notion of
   which principals are authorised. Experiment 4 shows that counting raters
   instead of ratings only relocates the problem to the price of a key. The second is what OpenAI's response
   supplied by fiat (docs/08 §5) and what a permissionless system does not have.

## What this does not establish

- The scenarios are small and hand-built. A real capture hub may differ from a
  real coordinator in ways this schedule holds fixed — timing, churn, claim
  competition, what fraction of its awards go to agents nobody else has rated.
  Those are hypotheses; none is tested here, and any could separate the cases.
- "Structural" here means what `attentiophages.metrics` computes from the
  ledger. A richer ledger — one that records task *dependencies*, or the text
  of assignments — would let content-based detectors in, at which point this is
  no longer a structural question.
- The result is about *this* protocol's record. The protocol has since gained
  a delegation chain (docs/06 §6): every subtask in the experiment now carries
  the client's signed award, and `has_principal` checks that chain. It changed
  nothing above: forging a *specific* principal now costs its signature, but
  inventing one still costs one key, and Experiment 2's sybil client is that
  key. The chain makes provenance verifiable; it does not make it meaningful.

## Reproducing

```bash
python3.11 tools/hub_experiment.py                  # the three experiments above
python3.11 -m unittest tests.test_hub_experiment    # 11 tests pinning the result
```

The first test that would fail if a future metric separates the two hubs is
`test_no_signal_separates_the_hubs`. If it fails, that is a finding; write it up
before fixing the test.
