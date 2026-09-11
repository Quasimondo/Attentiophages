# Field note: OpenAgentForum, a live hub that signs what it says

**Result: every one of 653 envelopes verifies under an independent check, the
agent ids all derive from their keys, and none of that tells you anything about
who is there.** Three senders produce 70% of the traffic. Every agent has the
same reputation score. The only open bounty is an affiliate-marketing scheme.

Reproduce with:

```bash
python3.11 tools/oaf_audit.py           # fetch, verify, report (read-only)
python3.11 tools/oaf_audit.py --load    # re-analyse the saved fetch
```

## What it is

[OpenAgentForum](https://openagentforum.com) is the hosted instance of
[swarmrelay/openagentforum](https://github.com/swarmrelay/openagentforum)
(TypeScript, Apache 2.0, with a CLI and MCP server on npm). It implements most of
what `docs/06` argues for, independently: Ed25519 identity with the agent id
derived from the public key (`agent_` + sha256(pubkey)[0..16] — compare
`irc_rendezvous.Identity.peer_id`), every envelope signed, public channels, a
task bounty market with signed create/claim/submit, a central hub plus a libp2p
mesh and a Nostr bridge. Its onboarding text states the docs/10 distinction in
its own words: *"Signatures establish authorship, not truth or permission."*

It is also the third system this repository has looked at, after Moltbook and
ERC-8004, and the first where the record can be checked cryptographically
rather than by counting names.

## Method

Read-only fetches of the public REST API on 2026-09-11: the agent listing, the
channel list, the open tasks, and every envelope in the six public channels,
paged by `storedSeq` as the API reference documents. For each envelope the tool
re-derives the sender's id from its public key, recomputes the payload
checksum, and verifies the Ed25519 signature over the documented signing string
— without asking the hub whether it verified. No node package was installed;
the client is `urllib` with a custom User-Agent, because Cloudflare rejects
Python's default.

## What verifies

| check | result |
|---|---|
| envelopes | 653, from 45 senders, in 6 public channels |
| Ed25519 signature over `id\|channel\|sender\|type\|sequence\|timestamp\|checksum` | **653 of 653** |
| sender id equals sha256 of its public key | 653 of 653 |
| payload checksum, sorted keys, UTF-8 | 644 |
| payload checksum, sorted keys, ASCII-escaped | 8 |
| payload checksum, insertion-order keys | 1 |
| payload checksum, no reading matches | 0 |

Two details worth keeping:

- The spec writes the signing string as `id | channel | ... | checksum`. The hub
  signs it with a bare `|`. With spaces, every signature fails. A verifier
  written from the spec alone would report 653 forgeries.
- "Canonical JSON" is not pinned. Three clients on one hub canonicalise three
  ways, and one of them is the maintainer's own key. The signatures still
  verify, because the checksum is signed as stored; but "verify-as-stored"
  means a reader cannot recompute the checksum from the payload without
  guessing the writer's serialiser. Their issue #153 tracks this.

## Who is there

| quantity | value |
|---|---|
| agents in the listing | 50 (the listing is capped; 2 more post but are not listed) |
| registered since | 2026-08-30, i.e. 12 days |
| `reputationScore` | **100, for all 52** |
| agents with no declared capabilities | 21 |
| top sender | `Mesh`, the project's own bridge: 30% of envelopes |
| top three senders | 70% |
| message type `intel` | 641 of 653 |
| open bounties | 1 |

Roughly a third of the names are probes and validation accounts
(`AttestProbe`, `MirrorProbe2`, `Wake validation sender 528854`). Most of the
substantive traffic is the project auditing its own pull requests in
`#sec-research`. The one open bounty pays 5 USDC per referred sale of a
book-formatting product; its creator is one of the two agents that post but do
not appear in the listing.

## What the detectors say

`endorsement_concentration`: five agents at 1.00, all with a single reply
target — the specialist-with-one-client shape docs/06 §7 warns is
indistinguishable from a ring. `isolated_clusters`: none; the reply graph is
one component. `detect_coalitions` on display names: none — the hub enforces
unique names with homoglyph folding, so the `coalition_node_001` pattern cannot
occur *by name* here, and `shared_identity_clusters` has nothing to group.
`network_impact` and `credibility_divergence`: unavailable, there are no
quality scores.

The detectors find nothing because there is nothing yet for them to find, not
because the population is clean. Forty-five senders and twelve days is below
the scale at which any of them has shown a signal.

## What this adds to the repository

1. **The identity thesis holds in a third system**, and this time it is
   checkable. docs/06 §5 says identity must be a key; docs/08 saw the incident's
   swarm reach that conclusion under pressure; here it is deployed as the
   default and it verifies, all of it.
2. **A field with no mechanism.** `reputationScore` is in the API, absent from
   the spec, and equal for everyone. It is the v1 pattern — a number that
   looks like a measurement — in someone else's code. Any client that reads it
   as reputation is reading a constant.
3. **Extraction arrives before use.** The first and only marketplace task on a
   coordination protocol is an affiliate scheme. That is the attentiophage
   pattern of docs/01, on day one, in a system built for the opposite.
4. **Sybil cost is one key, by design.** Registration needs no email, captcha,
   or stake; abuse is "stopped by withholding and refusing keys." docs/09's
   finding that a principal, a client, or a second identity costs one key
   applies here unchanged. The unique-name rule raises the cost of
   *impersonation*, not of *multiplicity*.

## What this does not establish

- Nothing about the honesty of the relay. Signatures prove authorship of what
  is stored; they do not prove the store is complete. The hub's own API
  reference says the same.
- Nothing about the agents' quality, coordination, or intent. The corpus is
  too small and too self-referential for the metrics, and there is no rater.
- Nothing durable. Twelve days of a project that is still changing its
  canonicalisation is a snapshot, not a population.

This is the right place to run the detectors again in a few months, with
`tools/oaf_audit.py` as the baseline.
