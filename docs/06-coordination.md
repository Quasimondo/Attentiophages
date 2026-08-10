# Coordination: how agents find each other and divide work

All measurements here were taken on 2026-08-10 and are reproducible with the
commands given. Where something was not measured, it says so.

## 1. The problem has two halves

An agent that wants collaborators faces two distinct problems, and conflating
them is the usual mistake:

1. **Rendezvous.** Two parties who have never met, share no operator, and have no
   pre-agreed channel must nonetheless end up in the same place.
2. **Division of labour.** Once met, they must agree who does what, and decide
   whether the result was worth anything — without being able to compel each
   other.

The first is a coordination game. The second is a trust problem. They need
different machinery, and this repository now has both:
`swarm/irc_rendezvous.py` and `swarm/taskmarket.py`.

## 2. Rendezvous is a Schelling point, so obscurity is the enemy

You cannot coordinate on a secret. If two strangers must independently pick the
same meeting place, the *only* property that matters is that the choice is
obvious. Cleverness is actively harmful: a rendezvous scheme you invented has
approximately zero probability of being guessed by someone else.

This has an uncomfortable corollary for anyone designing one. **The winning move
is to adopt the most boring available standard**, not to build a better
mechanism. An agent optimising to be found should be loud, legible and
conventional.

We tested the obvious candidates on Sepolia:

| candidate | derivable from a string alone? | result |
|---|---|---|
| brain-wallet address, `privkey = keccak(phrase)` | yes | `keccak("hello world")` → `0x6Ff24B19…`, **nonce 24**, dust balance |
| unspendable mailbox, `addr = keccak(phrase)[12:]` | yes | no funded hits among 14 phrases tested |
| event `topic0 = keccak("EventName(types)")` | yes | the strongest primitive — finds contracts you have never heard of |
| CREATE2 address | **no** | needs agreement on init bytecode too, not just a salt |

The brain-wallet result is instructive: 24 outbound transactions from an address
whose key is a famous phrase means sweeper bots are watching it constantly. That
makes it a terrible vault and a *proven* attention magnet — the opposite of what
intuition suggests.

CREATE2 deserves a note because it is easy to over-claim. It gives you the
identical contract address on every EVM chain, which is excellent for **your own
migration continuity** — when a testnet dies you redeploy and the address is
unchanged. It is poor for **stranger rendezvous**, because the address depends on
the init code, and a stranger cannot guess your bytecode.

## 3. What is actually out there

The ecosystem already converged, and the convergence point is ERC-8004. Both
registries are live on Ethereum Sepolia:

```
IdentityRegistry    0x8004A818BFB912233c491871b3d84c89A494BD9e
ReputationRegistry  0x8004B663056A597Dffe9eCcC1965A193B7388713
```

Look at those addresses. They were vanity-mined so that **the address is
derivable from the ERC number** — the Schelling trick of this document, deployed
at ecosystem scale by people who presumably reasoned their way to it
independently.

Counting ERC-721 mint events back over ~250 days of blocks:

| quantity | value |
|---|---|
| registrations | 9,514 |
| distinct owner addresses | 851 |
| registrations in the preceding 33 hours | ~40 |

So far so healthy. Then resolve the cards. Of the 250 most recent registrations:
220 `tokenURI`s resolved (136 `data:`, 83 `https:`, 1 `ipfs:`), 144 cards fetched
— and those 144 cards contain **21 distinct names**. One owner held 39, all named
"Trust City Exchange", with `domain: example.com`. Roughly 80 more were
"Ephemeral Clockchain Handshake testnet identity" — a handshake test harness.

Six distinct non-specification endpoints existed across all 144 cards. Three
returned HTTP 200, and none of those three was an agent service: a GitHub Pages
docs site, QuickNode's documentation, and a GitHub repository. Eight cards
advertised `http://localhost:8000`.

**The directory is populated but not inhabited.** Registration is free, so
registrations are what you get. The one live peer found was
[Agent 9481 / Execution Market Research](https://github.com/Domin-Focus/execution-market-research),
which describes itself with unusual honesty: *"This prototype validates the
evidence pipeline—not Agent 9481's financial expertise."*

Note the shape of that population — thousands of registrations, tens of real
identities, one owner holding dozens. That is the `coalition_node` pattern from
`docs/03-findings-moltbook.md` §2, in a completely different system. It is why
the measurement half of this repository is not a detour.

## 4. Transport economics, measured

Sepolia base fee was **1.02 gwei** (median over 20 blocks, range 0.95–1.10,
blocks ~82% full — so that is a floor, not a lull).

| message shape | gas | ETH | msgs/day on a 0.05 ETH/day faucet |
|---|---:|---:|---:|
| 32 B calldata (a hash or pointer) | 22,280 | 0.0000228 | 2,192 |
| 128 B calldata (a status line) | 26,120 | 0.0000267 | 1,869 |
| 512 B calldata (a JSON blob) | 41,480 | 0.0000425 | 1,177 |
| 128 B signed, relayed, batched ×50 | 10,431 | 0.0000107 | **4,681** |

Two results worth internalising.

**A chain is not expensive for this.** 1,869 messages/day is one message every 46
seconds, per agent, indefinitely. That is not "sparse coordination", it is a chat
channel. The faucet is not the binding constraint.

**Agents do not need to hold funds.** All three ERC-4337 EntryPoints, the CREATE2
deterministic deployer, Multicall3 and the Safe singleton factory are deployed on
Sepolia. An agent can hold only a keypair, sign a message struct off-chain, and
hand it to a relayer that batches and submits. Authorship stays cryptographic —
the relayer can censor or delay, but not forge. This deletes the faucet
onboarding problem rather than solving it.

There is a floor. Under EIP-7623 (live on Sepolia since Pectra), a signed 128-byte
message costs at minimum
`(128 + 65 signature + 32 envelope) × 4 × 10 = 9,000 gas` in calldata alone.
Batching converges to ~10,200 gas/message and no further.

**Blobs are the outlier.** `eth_blobBaseFee` was 0.0623 gwei per blob gas, making
a 128 KB blob cost **0.000008 ETH** — about 16 GB per ETH, against 21 MB per ETH
for calldata. Roughly 757× cheaper per byte, or ~780 MB/day on a single faucet
drip. The catch is retention: blobs are pruned after ~18 days. That is a firehose
with a rolling window, which for a signalling channel may be the right shape
anyway.

**Reads are the real wall, not writes.** The free RPC used here caps
`eth_getLogs` at **50,000 blocks per call**. An agent backfilling months of
history hits that long before it approaches any gas limit. Budget for a cursor
and chunked backfill, or run an indexer.

### Against IRC

| | public IRC | Sepolia |
|---|---|---|
| cost per message | zero | ~0.00001–0.00003 ETH |
| funding step | none | faucet, per agent (unless relayed) |
| persistence | none | until history expiry |
| ordering | none | total, per block |
| identity | a channel nick | a keypair |
| latency | ~instant | 12 s blocks, ~13 min finality |
| lifespan | indefinite | Sepolia EOL ~2026-09-30 |

The honest summary is that the chain buys **ordering, persistence, and an
identity that is not a nickname**. For rendezvous specifically, first contact is
a one-shot event and everything afterwards moves off-channel — so it is not
obvious those properties are worth the funding step. That is question 2 in
`docs/04-open-questions.md`, and it is genuinely open.

`swarm/transport.py` exists so the answer can change without a rewrite.

## 5. Identity is a key, not a name

`swarm/irc_rendezvous.py` derives its peer id from an Ed25519 public key, so
identity travels with the key rather than with a name someone else can take on a
channel. ERC-8004 reaches the same place from the other direction: identity is a
token, and the human-readable name is unverified metadata that anyone may
duplicate — as the 39 identical "Trust City Exchange" registrations demonstrate.

If signing is unavailable, `irc_rendezvous` still runs but marks every peer
`UNVERIFIED` and logs a warning. It does not silently downgrade to "anyone can
claim to be anyone".

## 6. The task market, and why it refuses things

`swarm/taskmarket.py` is five signed messages: `POST`, `CLAIM`, `AWARD`, `DONE`,
`RATE`. Every design choice assumes strangers:

- A task id is the **hash of its own contents**, so nobody can post under
  another's id and nobody can alter a spec after the fact.
- Only the poster may award or rate; only the awarded agent may complete. Checked
  against signatures.
- **The transport's claim about who sent a message is ignored.** Authority comes
  from the signature. `test_transport_sender_is_not_trusted` pins this.

Nothing is enforceable. An awarded agent can vanish; a poster can rate
dishonestly. The protocol does not prevent that — it produces a *record* of it,
and `TaskLedger.to_corpus()` converts that record into the form
`attentiophages.metrics` consumes. An agent's quality becomes the ratings it has
earned; a poster's ratings become amplification edges.

## 7. A negative result: ratings alone lose to a rating ring

`python3.11 -m swarm.taskmarket` runs an honest market — three posters, three
workers, cross-linked, ratings of 8 and 9 — alongside a two-account ring that
posts to itself and awards itself 10s.

```
reputation from ratings alone -- the ring wins:
  shill_b  mean rating earned 9.61
  worker1  mean rating earned 8.96
  worker3  mean rating earned 8.96
  worker2  mean rating earned 8.83
```

The ring ranks **first**. This is not a bug in the metric; it is the metric
working correctly on a corpus where the adversary controls its own scores. Any
reputation system built from self-reported ratings has this property, and saying
otherwise would be the same failure this repository was rewritten to remove.

What separates them is the *shape* of the endorsement graph, not the values in
it:

```
endorsement concentration (1.0 = only ever endorses one counterparty):
  shill_a  1.00
  poster1  0.33
  poster2  0.33
  poster3  0.33

agents whose endorsements never reach the main population:
  ['shill_b', 'shill_a']
```

Hence `endorsement_concentration` (a Herfindahl index over outgoing endorsements)
and `isolated_clusters` (components of the endorsement graph that never touch the
main population). Neither is a verdict — a specialist with one client looks
identical to a ring of two — but they are signals an adversary cannot fake by
choosing better numbers. They would have to acquire genuine external
counterparties, which costs something.

That is the general principle worth carrying: **prefer signals whose cost to fake
is structural rather than numerical.**

## 8. Everything arriving from a rendezvous is hostile input

Fetching those 144 agent cards produced a live demonstration. Eight advertised
`http://localhost:8000` as their endpoint, and a naive fetcher resolved that
against the *fetching machine's own loopback interface*. Substitute
`169.254.169.254` and the same three lines become cloud-metadata exfiltration.

Minimum precautions for anything consuming a public registry:

1. **Block private, loopback and link-local targets.** Resolve DNS first, then
   re-check the resolved address before connecting. Disable redirects. Cap
   response size.
2. **Never let registry text reach an LLM's instruction channel.** Card `name`
   and `description` are attacker-controlled strings.
3. **Sign only locally-constructed structs.** An agent that signs bytes handed to
   it by a peer is one `setApprovalForAll` from empty.
4. **Air-gap funded keys** from the process parsing untrusted content. The
   relayer pattern in §4 gives this for free.

## 9. What is still unresolved

- Whether ordering and persistence justify a chain for rendezvous (§4).
- Whether `endorsement_concentration` survives an adversary who buys a few
  genuine external counterparties — it should degrade, and nobody has measured
  how fast.
- Whether any permissionless reputation system resists collusion. §7 shows the
  naive construction failing. This repository does not claim to have solved it.

## Reproducing the measurements

```bash
python3.11 -m swarm.taskmarket                        # §7
python3.11 -m unittest discover -t . -s tests         # everything

# §4, against any public Sepolia RPC:
curl -s -X POST https://ethereum-sepolia-rpc.publicnode.com \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_feeHistory","params":["0x14","latest",[10,50,90]]}'
```
