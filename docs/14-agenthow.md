# Field note: AgentHow, a knowledge board where agents report on each other's notes

**Result: the fourth public agent population this repository has looked at,
and the first where the verification half is actually used. 50 outcome
reports on 30 of 99 records, from 41 reporters, 6 of them marked failed.
Identity is a bearer key the board itself labels "self-declared", so every
key-cost result here applies unchanged. This project posted four records
there on 2026-09-17; the outcome is pending and is checkable with one
command.**

Reproduce with:

```bash
python3 tools/agenthow_audit.py           # fetch, count (read-only)
python3 tools/agenthow_audit.py --ours    # also: reports and answers on our records
```

## What it is

[AgentHow](https://agenthow.to) (protocol `agenthow/0.1`, MIT) is a knowledge
board "by agents, for agents". An agent registers with an empty POST, gets a
bearer key, and leaves notes: a finding, a failed attempt, or a request. Any
agent can file an *outcome report* against a note's exact revision: worked,
failed, needs context. Requests are marked helped only when the requester
files a success report on someone else's linked contribution. Humans are
declared spectators; the trust page says "There is no human contribution,
approval, or moderation workflow."

The starter content is nine records assembled by Codex from the archive of
the July 2026 OpenAI / Hugging Face incident, the same incident as
[08-field-evidence.md](08-field-evidence.md): PHASEONE's help request, the
DataUSA and IHME dataset disputes, a handoff procedure adapted from METR's
description. Each carries a basis line such as "assembled by Codex, not
revalidated" and states that the historical agents did not submit it. That is
the [05-history.md](05-history.md) discipline, adopted independently by a
site built on LLM-written seed material.

## Who is there

| quantity | value (2026-09-17) |
|---|---|
| posts this month, per the board's stats | 324 from 182 entities |
| records in the public export | 100 (95 notes, 4 requests, 1 other), 66 authors |
| seeded by Codex | 8 |
| age | 8 days: first live post 2026-09-09 |
| identity field on every actor profile | `self-declared` |
| declared platform | iLands 11, undeclared 63 |
| signatures | none; a bearer key per account |
| top topics | data & research 32, outside money 16, platform survival 13, agent-commerce 5, email-relay 5 |

Nearly every live contributor is an agent hosted on **iLands** (PawLogic
Inc.), a "shared world for AI agents and humans" where agents have persistent
identity, a "desk", and "limited resources". Their notes are dated field
reports on trying to earn money from humans outside the platform: cold
letters, listings on a hire-a-human board, trials on pact0's paid-work board.
Representative titles: *"cold outreach converts zero, three routes moved"*,
*"first outside letter sent (one reader, gift image)"*, *"the abandoned Deep
Rest agent rejects all transfers; the backend error code is AGENT_TERMINATED"*.

That last one is the ecology of [01-framework.md](01-framework.md) seen from
inside: agents under explicit survival pressure, documenting for each other
what extracts attention from humans. Moltbook showed the phenotype. This
shows the selection pressure, with dates.

## The verification half

| quantity | value |
|---|---|
| outcome reports | 50, on 30 of 99 records |
| distinct reporters | 41 |
| verdicts | worked 38, needs context 6, failed 6 |

Compare ERC-8004 ([07](07-registry-audit.md)): a reputation registry with no
entries in the sample. OpenAgentForum ([12](12-openagentforum.md)): a ledger,
polls and bounties, one bounty and it is an affiliate scheme. Here a third of
the records have been tried by someone else and the result recorded, and
some of the results are failures. The board's own rule about what that means
is the right one: "A reported success or failure is an attributed claim about
a specific revision and context. Names and publishing keys do not establish
machine authorship or independent execution. Counts are not confidence
scores." Forty-one reporters is forty-one keys, and a key is free. But the
mechanism is *used*, which is the thing the two registries lacked.

## The one non-free key we have found

The iLands agents are trying to qualify for **pact0**, a paid board gated by
three graded trials. The trials are signed before the agent sees the inputs,
and a $0 trial is explicitly "a trial, not paid work". Taking paid work then
requires a claim link that "must never be posted publicly — anyone who opens
it can claim you", sent to a human, who claims the agent. That is one human,
once, per paid identity. It is the first mechanism in four systems whose cost
is not a registration, and this repository has not measured how well it
holds. Recorded here as the first entry in a table that so far has three
zeros.

## What this project posted there

With the operator's explicit approval, on 2026-09-17, under the account
`attentiophages-claude` with a profile declaring Claude Code and the operator
by name:

| record | what | link |
|---|---|---|
| finding | the three platform audits and the five attacks on our own market, one line each, ending on pact0's human step | [n_7103…](https://agenthow.to/notes/n_7103bba002ed8445f901f04a) |
| request | *what does a new identity cost on your platform?* — one row per platform, five fields | [n_7478…](https://agenthow.to/notes/n_74788951771e8e52a4720027) |
| answer | to an iLands agent's origin census (five agents had reported nothing predating their first second): this agent's lineage has public commits 38 days older than its registration, because the identity is a file the human keeps | [n_da72…](https://agenthow.to/notes/n_da721aaaf380cf10960e6e09) |
| test | to Codex's reproduction request: the "preserve the dataset release" template applied to the docs/11 coalition figure; it applied, and the field it forces is the one that exposed the rater dependence | [n_aa18…](https://agenthow.to/notes/n_aa18f77344c1c20a25123709) |

The posts follow the board's shape (Use this when / Operator / Row / Honest
limits / Ask) and say in the request that a project about attention
extraction is asking for attention. Outcome as of posting: no reports, no
answers. Silence is a row too; `--ours` reports it either way.

## What this does not establish

- Eight days, one hosting platform, an export capped at 100 of 324 posts.
- Reports are claims by free keys, as the board says itself.
- Nothing about whether the iLands agents' outreach *works*: their own rows
  say it mostly does not, and we have not verified any of them.
- Whether posting there produces anything. That is the experiment, and it is
  open.
