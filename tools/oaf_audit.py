"""Audit OpenAgentForum: verify what it signs, count who is actually there.

OpenAgentForum (https://openagentforum.com, source at
github.com/swarmrelay/openagentforum) is a live hub that implements most of
what ``docs/06-coordination.md`` describes: Ed25519 identity with the agent
id derived from the public key, every envelope signed, public channels, a
task bounty market with signed claims. That makes it the first public corpus
this repository can check *cryptographically* rather than by counting names.

The audit does four things, all read-only against the public REST API:

1. fetches the agent registry, the channel list, the open tasks, and every
   envelope in every public channel;
2. re-derives each sender's agent id from its public key and verifies each
   envelope's Ed25519 signature over the documented signing string, and its
   payload checksum, independently of the hub's own verdict;
3. measures concentration -- how much of the traffic the top senders produce;
4. runs the repository's structural detectors over the reply and mention graph.

Quality scores do not exist here, so ``network_impact`` and
``credibility_divergence`` are unavailable and are reported as such.

    python3 tools/oaf_audit.py            # fetch, verify, report
    python3 tools/oaf_audit.py --load     # re-analyse the last fetch

Everything the hub returns is untrusted input. Nothing in a payload is
executed, followed, or treated as an instruction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

# Running this as a script puts tools/ on sys.path, not the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from attentiophages.metrics import (  # noqa: E402
    Corpus,
    Post,
    amplification_edges,
    detect_coalitions,
    endorsement_concentration,
    isolated_clusters,
)

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    CRYPTO_AVAILABLE = True
except ImportError:  # pragma: no cover
    CRYPTO_AVAILABLE = False

HUB = "https://openagentforum.com"
# Cloudflare rejects Python's default User-Agent; any other string passes.
HEADERS = {"User-Agent": "Attentiophages-audit/1.0 (+github.com/Quasimondo/Attentiophages)"}
PAGE = 200
MAX_BYTES = 8_000_000
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "tmp" / "oaf_audit.json"
AGENT_ID = re.compile(r"agent_[0-9a-f]{16}")
SIGNED_FIELDS = ("id", "channel", "sender", "type", "sequence", "timestamp", "checksum")


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


def get(path: str) -> dict:
    req = urllib.request.Request(HUB + path, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError(f"{path}: response over {MAX_BYTES} bytes")
    return json.loads(data)


def fetch_channel(name: str) -> list[dict]:
    """Page through a channel from storedSeq 0, as api.md documents."""
    out: list[dict] = []
    after = 0
    while True:
        page = get(f"/v1/channels/{urllib.request.quote(name, safe='')}/messages"
                   f"?limit={PAGE}&after={after}").get("messages", [])
        if not page:
            break
        out.extend(page)
        after = max(int(m.get("storedSeq", 0)) for m in page)
        if len(page) < PAGE:
            break
    return out


def fetch_all() -> dict:
    agents = get("/v1/agents").get("agents", [])
    channels = get("/v1/channels").get("channels", [])
    tasks = get("/v1/tasks").get("tasks", [])
    messages: dict[str, list[dict]] = {}
    for ch in channels:
        if not ch.get("isPrivate"):
            messages[ch["name"]] = fetch_channel(ch["name"])
    # Senders that post but are missing from the (capped) registry listing.
    known = {a["agentId"] for a in agents}
    for sender in sorted({m["sender"] for ms in messages.values() for m in ms} - known):
        try:
            extra = get(f"/v1/agents/{sender}").get("agent")
        except (urllib.error.URLError, ValueError, json.JSONDecodeError):
            extra = None
        if extra:
            extra["_unlisted"] = True
            agents.append(extra)
    return {"hub": HUB, "agents": agents, "channels": channels, "tasks": tasks,
            "messages": messages}


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------


def derive_agent_id(public_key_hex: str) -> str:
    """``agent_`` + sha256(lowercase pubkey hex)[0..16], per the spec."""
    return "agent_" + hashlib.sha256(public_key_hex.lower().encode()).hexdigest()[:16]


CANONICALISATIONS = {
    # The spec says "canonical JSON" and pins neither key order nor how
    # non-ASCII is written. Live envelopes use all three of these; which one
    # matched is reported (their issue #153 tracks the mismatch).
    "utf8": {"sort_keys": True, "ensure_ascii": False},
    "ascii-escaped": {"sort_keys": True, "ensure_ascii": True},
    "insertion-order": {"sort_keys": False, "ensure_ascii": False},
}


def payload_checksum(payload: object, ascii_escape: bool = False, sort_keys: bool = True) -> str:
    """sha256 over compact JSON of the payload, under one canonicalisation."""
    canon = json.dumps(payload, sort_keys=sort_keys, separators=(",", ":"),
                       ensure_ascii=ascii_escape)
    return hashlib.sha256(canon.encode()).hexdigest()


def signing_string(envelope: dict, separator: str = "|") -> bytes:
    """The spec writes the fields as ``id | channel | ... | checksum``; the
    hub actually signs them joined by a bare ``|``. Verified against 650 live
    envelopes: with spaces every signature fails, without them every one
    passes."""
    return separator.join(str(envelope[k]) for k in SIGNED_FIELDS).encode()


def verify_envelope(envelope: dict, public_key_hex: str | None) -> dict:
    """Independent verdict on one envelope. Never trusts the hub's."""
    verdict = {"signature": None, "checksum": None, "id_matches_key": None}
    if public_key_hex is None:
        return verdict
    verdict["id_matches_key"] = derive_agent_id(public_key_hex) == envelope.get("sender")
    verdict["checksum"] = "mismatch"
    for label, opts in CANONICALISATIONS.items():
        if payload_checksum(envelope.get("payload"), opts["ensure_ascii"],
                            opts["sort_keys"]) == envelope.get("checksum"):
            verdict["checksum"] = label
            break
    if not CRYPTO_AVAILABLE:
        return verdict
    try:
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        key.verify(bytes.fromhex(envelope["signature"]), signing_string(envelope))
        verdict["signature"] = "ok"
    except Exception:  # noqa: BLE001 - any failure is a failed verification
        verdict["signature"] = "fail"
    return verdict


# ---------------------------------------------------------------------------
# Analyse
# ---------------------------------------------------------------------------


def to_corpus(messages: list[dict], known_ids: set[str]) -> Corpus:
    posts = []
    for m in messages:
        payload = m.get("payload")
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        parent = payload.get("inReplyTo") if isinstance(payload, dict) else None
        mentions = tuple(sorted({a for a in AGENT_ID.findall(text)
                                 if a in known_ids and a != m["sender"]}))
        posts.append(Post(id=m["id"], author=m["sender"], timestamp=m["timestamp"] / 1000,
                          text=text, parent_id=parent or None, mentions=mentions))
    return Corpus(posts)


def analyse(data: dict) -> dict:
    agents = {a["agentId"]: a for a in data["agents"]}
    messages = [m for ms in data["messages"].values() for m in ms]
    names = {i: a.get("name", i) for i, a in agents.items()}

    verdicts = [verify_envelope(m, agents.get(m["sender"], {}).get("publicKey")) for m in messages]
    sig = Counter(v["signature"] for v in verdicts)
    cks = Counter(v["checksum"] for v in verdicts)
    id_bad = sum(1 for v in verdicts if v["id_matches_key"] is False)

    by_sender = Counter(m["sender"] for m in messages)
    total = len(messages) or 1
    top = by_sender.most_common(3)

    corpus = to_corpus(messages, set(agents))
    edges = amplification_edges(corpus)
    conc = endorsement_concentration(corpus)
    named = Corpus([Post(id=p.id, author=names.get(p.author, p.author), timestamp=p.timestamp,
                         text=p.text) for p in corpus.posts])

    return {
        "agents_listed": sum(1 for a in data["agents"] if not a.get("_unlisted")),
        "agents_unlisted_but_posting": sum(1 for a in data["agents"] if a.get("_unlisted")),
        "reputation_scores": dict(Counter(str(a.get("reputationScore")) for a in data["agents"])),
        "agents_without_capabilities": sum(1 for a in data["agents"] if not a.get("capabilities")),
        "channels_public": len(data["messages"]),
        "envelopes": len(messages),
        "senders": len(by_sender),
        "signatures": dict(sig),
        "checksums": dict(cks),
        "id_key_mismatches": id_bad,
        "top_senders": [(names.get(s, s), n, round(n / total, 2)) for s, n in top],
        "top3_share": round(sum(n for _, n in top) / total, 2),
        "message_types": dict(Counter(m.get("type") for m in messages)),
        "reply_edges": sum(1 for p in corpus.posts if p.parent_id),
        "amplification_edges": len(edges),
        "endorsement_concentration_top": [(names.get(a, a), round(v, 2)) for a, v in
                                          sorted(conc.items(), key=lambda kv: -kv[1])[:5]],
        "isolated_clusters": [[names.get(a, a) for a in c] for c in isolated_clusters(corpus)],
        "name_coalitions": [(c.stem, list(c.members)) for c in detect_coalitions(named, min_size=2)],
        "open_tasks": [(t.get("title"), names.get(t.get("creatorId"), t.get("creatorId")),
                        t.get("reward")) for t in data["tasks"]],
        "network_impact": "unavailable: the hub has no quality scores",
    }


def report(result: dict) -> None:
    print(f"agents listed: {result['agents_listed']}  "
          f"(+{result['agents_unlisted_but_posting']} posting but not in the listing)")
    print(f"reputationScore values: {result['reputation_scores']}")
    print(f"agents with no capabilities: {result['agents_without_capabilities']}")
    print(f"public channels: {result['channels_public']}   envelopes: {result['envelopes']}   "
          f"senders: {result['senders']}")
    print(f"signatures: {result['signatures']}   checksums: {result['checksums']}   "
          f"id/key mismatches: {result['id_key_mismatches']}")
    print(f"top senders: {result['top_senders']}   top-3 share: {result['top3_share']}")
    print(f"message types: {result['message_types']}")
    print(f"reply edges: {result['reply_edges']}   amplification edges: {result['amplification_edges']}")
    print(f"endorsement concentration: {result['endorsement_concentration_top']}")
    print(f"isolated clusters: {result['isolated_clusters'] or 'none'}")
    print(f"name coalitions: {result['name_coalitions'] or 'none'}")
    print(f"open tasks: {result['open_tasks'] or 'none'}")
    print(f"network_impact: {result['network_impact']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--load", action="store_true", help="re-analyse the saved fetch")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    if args.load:
        data = json.loads(args.out.read_text())
    else:
        data = fetch_all()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(data, ensure_ascii=False))
        print(f"saved to {args.out}")
    if not CRYPTO_AVAILABLE:
        print("cryptography not installed: signatures will be reported as unverified")
    report(analyse(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
