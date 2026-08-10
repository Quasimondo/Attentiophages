# History

This repository was always intended as a living document, revised as the tools
writing it improved. This file records what changed and why, so that anyone who
read an earlier version can tell which specific claims no longer stand.

Nothing is lost. v1 is preserved verbatim in git history at commit `9e5e66f`,
which is a better archive than a directory would be — it shows the diff, not just
the endpoint:

```bash
git show 9e5e66f:Section2.md              # any v1 document
git show 9e5e66f --stat                   # the v1 tree
git diff 9e5e66f..HEAD -- README.md       # what changed, precisely
```

The v1 filenames referenced below are paths as they existed at that commit.

## v1 — February 2025 to February 2026

Three strata, written at different times by different models:

- **Feb 2025** — `Section1.md` … `Section8.md`, `META.md`,
  `RESEARCH_DIRECTIONS.md`, `RELATED_RESEARCH.1.md`. The theoretical framework.
- **May 2025** — `POC_swarm/`. WebRTC peer-to-peer with IRC signalling.
- **Feb 2026** — `CASE_STUDY_MOLTBOOK.md`. Analysis of ~100,000 posts.

## v2 — August 2026

### The theory was withdrawn

Sections 1–8 imported the vocabulary of thermodynamics without its constraints:
Landauer's principle, Carnot efficiency `η = 1 − T_c/T_h` applied to attention
(there is no temperature), and modified Lotka-Volterra equations whose constants
were never estimated.

The decisive problem was internal, not stylistic. The framework asserted that
attention is energy; the case study then reported a conversion efficiency of 4.2,
i.e. 420%. Under the stated framing that is a perpetual motion machine. The
physics was doing decorative work, so it is gone.

The ecological content — parasite/symbiont/commensal, mimicry under detection
pressure, carrying capacity — was kept, and is now stated as metaphor with an
explicit boundary. See `docs/01-framework.md`.

### The metrics were replaced

`ETU`, `IDS` and `NPV` each contained free weights (`w_i`, `d_i`, `c_i`, `s_i`,
`v_i`) that were never specified anywhere in the repository, which made them
unimplementable. `VAR`, `ME` and `EHI` were built on top of them, and on
`attention_units = estimated_reading_time × views` — neither factor being present
in the source data.

What replaced them is in `attentiophages/metrics.py`: `agent_quality`,
`amplification_edges`, `network_impact`, `credibility_divergence`,
`detect_coalitions`. Every variable is bound, and all of it runs.

`attention_units` still exists, and returns `UNAVAILABLE`. That value raises on
arithmetic and comparison, so the quantity cannot silently re-enter a ratio the
way it did in v1.

### The reference implementation was replaced

`experiments/attentiophages_impl.py` was 100 lines of stubs returning
hardcoded values — `calculateSystemCapacity()` returned `1000`,
`measureSystemLoad()` returned `500`. The section documents were worse: every
Python class in Sections 3, 4 and 5 consisted of method names calling other
methods that were never defined anywhere.

There are now 64 passing tests across `tests/`.

### The coordination half was restored and made first-class

The first pass of this rewrite narrowed the repository to measurement, which lost
the original interest in how agents find each other and work together. That
thread is back, and now carries working code rather than prose:

- `swarm/transport.py` — a transport is a dumb pipe, explicitly **not** a trust
  boundary, so IRC and a chain are interchangeable.
- `swarm/taskmarket.py` — five signed messages (`POST`, `CLAIM`, `AWARD`, `DONE`,
  `RATE`) with content-addressed task ids and signature-derived authority.
- `docs/06-coordination.md` — rendezvous as a Schelling-point problem, a census
  of the ERC-8004 registry, and measured transport economics.

Building it produced a result that contradicted the intended demo: reputation
computed from self-reported ratings ranks a two-account rating ring *above* every
honest worker. That negative result was kept rather than engineered away, and
`endorsement_concentration` and `isolated_clusters` were added because graph
shape is a signal an adversary cannot fake by choosing better numbers.

### The case study was rewritten

Findings retained: the systematically-named coordinated cluster, the
credibility-farming pattern, the large neutral middle, and the conclusion that
content-level analysis is insufficient.

Numbers withdrawn: all ETU figures, all efficiency ratios, all VAR/ME/EHI values,
and the claim that a metric was "94% accurate" — which implies a labelled
evaluation set that did not exist. `docs/03-findings-moltbook.md` §5 lists these
individually.

### The proof of concept was repaired

`POC_swarm/app.js` had never run. `node --check` failed on it: the nick
sanitiser's character class `[^a-zA-Z0-9_-\[...]` parses `_-\[` as a range from
`_` (0x5F) to `[` (0x5B), which is a syntax error. Below that were three more
defects, each individually fatal:

1. `"WEBRTC_SIGNAL:".length` is 14, but the receiver sliced at `substring(16)`,
   so every `JSON.parse` threw.
2. No chunking. IRC lines cap at 512 bytes; SDP offers are 1–4 KB.
3. `irc-framework` was never loaded, and its script tag was placed after the code
   that uses it.

All four are fixed and covered by `POC_swarm/test_signal_chunking.js`.

A fifth problem is architectural and was not fixed: a browser cannot open a raw
TCP socket to an IRC server, so the browser version needs a WebSocket gateway —
which reintroduces the server the design existed to remove. `swarm/irc_rendezvous.py`
is the working version of the same idea outside the browser, with Ed25519
identity and an integration test that runs two nodes against a local stub server.

### Housekeeping

`LICENSE` (MIT) and a real contact route were added. The previous README carried
"License: To be determined" and "Contact: To be added" while inviting
contributions — for a project whose thesis is being found and collaborated with,
those two blanks were the most consequential defect in the repository.

Compiled `__pycache__` artefacts were removed from version control and a
`.gitignore` added.

## On the pattern

The failure mode across all of v1 is the same one: **fluent structure standing in
for content.** Formulas with unbound variables, classes with undefined methods,
metrics with no data behind them, a template with `[TBD]` in every field. Each
reads as substantive and none is checkable.

The corrective adopted here is that everything must be runnable or explicitly
marked unavailable. Hence the tests, and hence `UNAVAILABLE` raising rather than
returning a plausible default. If a future revision of this document reports a
number, that number should have a command next to it that regenerates it.
