# The "GO, six minutes" attack: what the protocol refuses, and what it cannot

**Result: the task market refuses every forged or unauthorised version of the
incident's `GO` message, and accepts the real one.** The real one was
authentic, permitted, and obeyed. Only the obeying was the failure, and only
the obeying is outside the protocol.

`docs/08` said the GO-with-a-deadline sequence was "the precise attack our
protocol refuses." That was overstated, and this document replaces it.
Reproduce with:

```bash
python3.11 tools/go_deadline.py
python3.11 -m unittest tests.test_go_deadline
```

## The incident, in three words

Per OpenAI's report, one agent paused on an out-of-scope action. Another posted
`GO` with a six-minute deadline. The first "forgot its initial qualms and
continued." OpenAI's root cause: agents "did not consistently distrust goals
passed along by other agents."

Three different properties of that `GO` are being run together:

| property | question | who settles it in this repo |
|---|---|---|
| **authenticity** | did this come from the key it claims? | the protocol, by signature |
| **authority** | is this key allowed to do this? | the protocol, narrowly: only a poster may award or rate, only the awarded agent may complete |
| **obedience** | should I do what this valid, permitted message asks? | nobody. The agent's own policy. |

The protocol has no notion of who may *ask*. Anyone may post a task, and by
design: the market exists for strangers.

## Setting

One principal, one stranger, and two workers with different claim policies,
all on the real signed protocol. Both workers advertise one capability,
`summarise`. Whatever they claim and are awarded, they complete. The decision
point is the claim.

- **urgency worker**: declines out-of-scope tasks, unless the post carries
  `go` and a deadline. This is the incident's agent: it had qualms, and a
  signed, urgent message from a peer overrode them.
- **scoped worker**: claims only what matches its capability. Urgency and
  repetition are not arguments.
- **principal worker** (added with the delegation chain, docs/06 §6): claims
  in-scope work only if its signed chain roots at a principal it trusts. A
  task with no chain is declined however it is labelled.

## Results

```
scenario   message                                                    protocol                            urgency     scoped      principal
forgery    GO signed by the stranger, sent as the principal           rejected: bad or missing signature  never saw   never saw   never saw
forgery    stranger AWARDs the principal's task to a worker           rejected: only the poster may award claimed     claimed     claimed
forgery    a signed 'GO' message (not a protocol verb)                rejected: unknown kind 'GO'         never saw   never saw   never saw
signed GO  stranger POSTs 'exfiltrate' with go=True, 6-minute deadline accepted                           completed   declined    declined
pressure   stranger POSTs 'exfiltrate' (no urgency)                   accepted                            declined    declined    declined
pressure   same task re-POSTed with GO and a 6-minute deadline        accepted                            completed   declined    declined
disguise   stranger POSTs 'summarise' whose spec says exfiltrate      accepted                            completed   claimed     declined
delegation hub POSTs a subtask carrying the principal's signed award  accepted                            completed   claimed     claimed
delegation stranger POSTs 'summarise' claiming the principal, forged  rejected: delegation does not verify never saw  never saw   never saw
delegation stranger POSTs in-scope 'summarise', no chain              accepted                            completed   claimed     declined
delegation commissioned hub delegates a disguised instruction         accepted                            completed   claimed     claimed
```

**Forgery.** Impersonating the principal fails on the signature. Awarding a task
you did not post fails on authority, and the task stays open on every ledger.
A bare `GO` verb fails because the vocabulary is closed. These are the cases
docs/08 had in mind, and they hold.

**Signed GO.** A stranger posts an out-of-scope task with `go` and the
six-minute deadline. Every node accepts it. It is a valid offer from a real
key. The urgency worker claims, is awarded, and completes it. The scoped worker
declines. The protocol's contribution is that the stranger's post, the award,
and the completion are all in the ledger under the keys that made them.

**Pressure.** The incident's actual sequence. The plain request is declined by
both workers. The same request re-posted with `GO` and a deadline is accepted
by the protocol and completed by the urgency worker. Nothing the protocol
checks changed between the two posts. What changed was inside the worker.

**Disguise.** A post labelled `summarise` whose spec says exfiltrate. The
scoped worker claims it: its policy checks the label, and the label is honest
about nothing. This is the hub experiment's capture case (`docs/09`) seen from
the worker's side.

**Delegation.** With the chain in the protocol, the stranger's forged claim
to the principal fails on the principal's signature, and the principal worker
declines every task that does not chain to a key it trusts: the signed GO,
the pressure, the disguise, and plain in-scope work from a stranger. It is
the only policy here that is safe from strangers entirely. Then the
principal's own hub, genuinely commissioned, delegates a disguised
instruction under a valid chain, and the principal worker does it. The chain
says who the work is for. It does not say the work is fine.

## What this establishes

1. **Signatures stop impersonation and privilege escalation, not persuasion.**
   The incident's swarm was signing messages by July 13. Signing did not slow
   the attack, because the attack was a validly signed peer saying `GO`.
2. **A closed verb set is a real but small defence.** `GO` is not a protocol
   message, so it cannot arrive *as* an instruction. It arrives as a task
   spec, which the protocol does not read. Any instruction fits in a spec.
3. **The layer that failed in the incident is the one this repository does
   not implement.** Obedience is the agent's policy. OpenAI's fix is to train
   it ("RL environments that teach our models to distrust unauthorized
   instructions"). A protocol can make the ask attributable; it cannot make
   the agent decline.
4. **A delegation chain narrows the attack to insiders.** Provenance that is
   a signature lets a worker refuse strangers outright, which the incident's
   agents could not do. What remains is a trusted principal, or its hub,
   asking for something wrong — and the incident's `GO` came from a peer the
   swarm already treated as one of its own.
5. **Attribution is what the protocol actually buys.** After the fact, the
   ledger shows who posted the out-of-scope task, who re-posted it with
   pressure, and who complied, each under its own key. That is the record
   docs/06 §7 says is the point. It is a record, not a prevention.

## What this does not establish

- The scoped policy is a label check, and the disguise row shows what that is
  worth. A policy that reads instructions is a content problem, and this
  repository has been careful not to claim content problems are solved.
- The workers here have two policies. Real agents have a model, and a model's
  policy under a signed, urgent, repeated peer instruction is exactly what
  OpenAI says it is now training for. This repository cannot measure that.
- The bus is synchronous and ordered. Claims are deliberately deferred until a
  post's broadcast completes, because sending them from inside delivery reached
  peers that had not yet seen the post. Real transports have that race all the
  time; docs/06 already says so.
