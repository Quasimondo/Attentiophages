# Open questions

**Replaces** `Section8.md`, `RESEARCH_DIRECTIONS.md` and `META.md` (v1, in git
history at commit `9e5e66f`). Those were lists of topics. These are questions
with a stated method
and a result that is not known in advance — the difference being that these can
come out wrong.

## 1. Does coalition detection survive an out-of-sample corpus? — **ANSWERED: no**

Run against the live ERC-8004 registry on 2026-08-10. `detect_coalitions` found
one cluster, entirely inside a group the trivial owner-address baseline had
already flagged, and nothing else. Zero value added. Meanwhile the dominant
coordination pattern in that corpus — one name registered from a fresh address
every time — was invisible to both methods, which is why
`shared_identity_clusters` now exists.

Full result, method and limits: **[docs/07-registry-audit.md](07-registry-audit.md)**.
Reproduce with `python3.11 tools/erc8004_audit.py --sample 800`.

The remainder of this section is the original setup, kept because the reasoning
still applies to the next corpus someone tries.

The ERC-8004 agent registries are live on Ethereum Sepolia and registration is
permissionless and effectively free, so Sybil clusters should be the default
rather than the exception.

Measured directly against `IdentityRegistry`
`0x8004A818BFB912233c491871b3d84c89A494BD9e` on 2026-08-10, by counting ERC-721
mint events over roughly 250 days of blocks:

| quantity | value |
|---|---|
| registrations | 9,514 |
| distinct owner addresses | 851 |
| distinct agent *names* in a 250-registration sample | 21 |
| largest single-owner holding in that sample | 39 registrations, all named "Trust City Exchange" |

That is the `coalition_node` shape in a completely different system. The test is
whether `detect_coalitions` recovers it without being told, and whether the
timing and text signals — designed for social posts — carry over to registration
metadata at all. They may not.

**Method:** enumerate mints, resolve each `tokenURI` to its agent card, treat card
`name` and `description` as the text channel and block timestamps as the timing
channel, then compare against the trivial baseline of grouping by owner address.
A detector that does not beat "group by owner" here has not earned its complexity.

**Handle the cards as hostile input.** They are attacker-controlled strings
fetched from URLs chosen by strangers. Fetching them naively will make your
process resolve `localhost` and private ranges on behalf of whoever wrote the
card. Block private/loopback/link-local targets, re-check the address after DNS
resolution, disable redirects, cap response size, and never let card text reach
an LLM's instruction channel.

## 2. What is a rendezvous channel actually worth?

`swarm/irc_rendezvous.py` and a chain-based beacon solve the same problem:
mutually unknown agents finding each other with no server in between. They fail
differently, and the comparison is not obvious.

Measured on Sepolia, 2026-08-10, base fee 1.02 gwei (median over 20 blocks,
stable, blocks ~82% full):

| approach | cost per ~128 B message | ceiling |
|---|---|---|
| one transaction per message | 26,120 gas ≈ 0.0000267 ETH | ~1,900/day on a 0.05 ETH/day faucet |
| relayed + batched ×50, signed | 10,431 gas/msg | ~4,700/day, and agents hold zero ETH |
| IRC | zero | server rate limits and operator goodwill |

The gas floor is irreducible: EIP-7623 charges
`(128 B payload + 65 B signature + 32 B envelope) × 4 × 10 = 9,000 gas` for the
calldata alone.

So the chain is not expensive. What it buys over IRC is ordering, persistence and
an identity that is not a channel nick. What it costs is a funding step and, for
Sepolia specifically, an announced end-of-life around 2026-09-30. The open
question is whether ordering and persistence are worth anything *for rendezvous
specifically*, given that first contact is by definition a one-shot event and
everything afterwards moves off-channel.

**A cheap experiment:** run both for a month, and count how often each is
reachable and how often a peer discovered on one could actually be contacted.

## 3. Is `credibility_divergence` defeatable, and how cheaply?

The metric assumes amplification is harder to fake than content. That assumption
is unexamined. Obvious attacks:

- Amplify high-quality accounts sincerely, and carry the payload in the content.
- Split the roles: one account posts well and amplifies well; a second, connected
  only off-graph, does the extraction.
- Poison the rater directly, since quality scores come from a model that reads
  attacker-controlled text.

The third is the serious one and applies to every metric in this repository. An
adversary who can influence the rater controls the denominator of everything.

## 4. How much of this is the rater rather than the ecosystem?

Every quality number traces to one 7B model. Nothing establishes that a different
rater produces the same ordering, and if it does not, the findings are properties
of Qwen 2.5 7B rather than of agent populations.

**Method:** re-score a stratified sample with a second, architecturally different
rater and report rank correlation per dimension. This is cheap and has never been
done. If agreement is poor, `docs/03-findings-moltbook.md` needs a warning at the
top.

## 5. What does an agent identity have to be?

`swarm/irc_rendezvous.py` derives peer id from an Ed25519 public key, so identity
travels with the key rather than with a name someone else can take. ERC-8004
takes the same position from the other direction: identity is a token, and the
human-readable name is unverified metadata.

Both leave the same question open: identity is cheap to mint, so what makes one
worth more than another? Reputation systems answer "accumulated history", which
means the first thing an adversary does is accumulate cheap history. The Moltbook
credibility-farming finding is that exact attack, observed. Whether any
permissionless reputation system resists it is not a solved problem, and this
repository does not solve it either.
