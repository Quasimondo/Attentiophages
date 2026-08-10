# Framework

**Replaces** `Section1.md` … `Section8.md` (v1, in git history at commit
`9e5e66f`). They are not a good starting point: they borrowed the vocabulary of
thermodynamics without any of its constraints, and their code was class skeletons
whose methods called other methods that were never defined. See
`docs/05-history.md`.

## The question

An agent operating in a shared information space consumes a finite resource —
other participants' attention — and returns something. The question this project
is about is narrow and empirical:

> Given only observable behaviour, can you tell whether an agent adds to the
> system it is in, or drains it?

Not whether it is intelligent, aligned, or well-intentioned. Whether the
observable record distinguishes it from an agent that is extracting.

## Why ecology, and where the borrowing stops

Ecology is the right source of metaphor because it studies exactly this: entities
competing for a finite resource, some of which are net contributors and some of
which are not, with selection pressure operating on the difference. Three
transfers are load-bearing:

- **Parasite / symbiont / commensal.** A three-way distinction, not two. The
  large middle category — organisms that take without meaningfully harming — has
  a direct counterpart in the data, and ignoring it produces confident
  misclassification of the majority.
- **Mimicry.** Where detection exists, mimicry of the protected category evolves.
  This predicted the most useful finding in the corpus before it was observed.
- **Carrying capacity.** A finite resource bounds a population regardless of how
  well individuals perform.

**The borrowing stops there.** In particular, this framework makes no
thermodynamic claims. Attention is not energy, there is no temperature, no
Carnot limit applies, and Landauer's principle says nothing about whether a post
was worth reading. v1 invoked all three, then reported conversion efficiencies
above 100% — which, had the physics been real, would have been a perpetual motion
machine. Metaphors that produce impossible results were doing decorative work.

A second stopping point: biological fitness is defined by reproduction, and
nothing here is. "Value" in this framework is whatever the rater was asked to
score. That is a human judgement wearing a number, and it should be argued about
rather than optimised.

## Definitions

Defined by observable behaviour, so they can be computed:

- **Extractive** — captures attention while its own output scores low, *or* while
  its amplification consistently directs attention to accounts that score low.
- **Contributive** — output scores well *and* amplification directs attention to
  accounts that score well.
- **Neutral** — neither, which in practice is most of the population.

Note that both definitions have two clauses, joined by the amplification graph.
That is the point of the framework, and it is the one thing the data actually
forced.

## The two claims that survived contact with data

**1. Per-post quality is not sufficient to classify an agent.**
An account can produce genuinely good posts and still be net extractive, by
spending the credibility those posts earn on directing attention elsewhere. This
was observed in the Moltbook corpus (`docs/03-findings-moltbook.md`, §3) and is
implemented as `credibility_divergence`.

**2. Any content-only detector is cheap to defeat.**
Producing plausible high-quality text is now approximately free. So a classifier
that reads only content is defeated by an adversary who simply writes well. The
amplification graph is harder to fake because it requires the cooperation of
accounts that are themselves visible and scoreable.

Both claims are about *where to look*, not about how to score. They are the
durable part of this project.

## What this framework does not claim

Stated explicitly, because v1 implied all of these:

- It does not claim agents "metabolise" anything, or that information processing
  in agents is thermodynamically constrained in any way that matters here.
- It does not claim population equilibria have been observed. That requires time
  series; only snapshots exist.
- It does not claim any metric has known accuracy. There is no labelled ground
  truth in this project, for anything.
- It does not claim these patterns generalise beyond the one corpus examined.
- It does not propose that agents *should* be built to maximise any score here.
  A metric that becomes a target stops measuring; that applies to these metrics
  as much as any other.

## What it is for

Two concrete uses, both defensive:

1. **Auditing a population** — given a corpus of agent activity, find coordinated
   clusters and accounts whose amplification behaviour contradicts their
   presentation.
2. **Auditing yourself** — if you operate agents, these are the measurements
   someone else would use on you.

The natural next corpus is permissionless agent registries, where registration is
free and Sybil clusters are consequently the default rather than the exception.
See `docs/04-open-questions.md`.
