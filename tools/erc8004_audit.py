#!/usr/bin/env python3.11
"""Out-of-sample test: point the coalition detectors at a live agent registry.

`docs/04-open-questions.md` §1 asks whether `detect_coalitions`, built from one
hand-found cluster in one social corpus, recovers anything on a completely
different system -- and whether it beats the trivial baseline of grouping
registrations by owner address. This runs that test against the ERC-8004
IdentityRegistry on Ethereum Sepolia.

The answer is not known in advance and a negative result is a real result.

Everything fetched here is attacker-controlled: agent cards are JSON at URLs
chosen by strangers. The fetcher below applies the precautions from
`docs/06-coordination.md` §8 -- private/loopback/link-local addresses blocked
after DNS resolution, redirects disabled, response size capped, and card text
treated strictly as data.

    python3.11 tools/erc8004_audit.py --sample 800
"""

from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Running this as a script puts tools/ on sys.path, not the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RPC = "https://ethereum-sepolia-rpc.publicnode.com"
ID_REGISTRY = "0x8004A818BFB912233c491871b3d84c89A494BD9e"
REP_REGISTRY = "0x8004B663056A597Dffe9eCcC1965A193B7388713"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ZERO_TOPIC = "0x" + "00" * 32
MAX_LOG_SPAN = 50_000          # this RPC rejects wider ranges
UA = {"user-agent": "curl/8.5.0", "content-type": "application/json"}
MAX_CARD_BYTES = 300_000


# --------------------------------------------------------------------------
# RPC
# --------------------------------------------------------------------------


def rpc_batch(calls: list[tuple[str, list]], timeout: int = 60,
              attempts: int = 6) -> list:
    """One batched JSON-RPC round trip, with backoff on 429.

    Public RPC endpoints rate-limit aggressively; a failed batch returns Nones
    rather than raising, so a partial result is visibly partial instead of
    aborting the whole audit.
    """
    payload = [
        {"jsonrpc": "2.0", "id": i, "method": m, "params": p}
        for i, (m, p) in enumerate(calls)
    ]
    data = json.dumps(payload).encode()
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(RPC, method="POST", headers=UA, data=data)
            body = json.load(urllib.request.urlopen(request, timeout=timeout))
            break
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == attempts - 1:
                if attempt == attempts - 1:
                    return [None] * len(calls)
                raise
            time.sleep(2.0 * (attempt + 1))
        except Exception:
            if attempt == attempts - 1:
                return [None] * len(calls)
            time.sleep(1.5 * (attempt + 1))
    else:
        return [None] * len(calls)

    if isinstance(body, dict):
        body = [body]
    out: list = [None] * len(calls)
    for item in body:
        index = item.get("id")
        if isinstance(index, int) and 0 <= index < len(calls):
            out[index] = item.get("result")
    return out


def rpc(method: str, params: list, timeout: int = 60):
    return rpc_batch([(method, params)], timeout=timeout)[0]


# --------------------------------------------------------------------------
# SSRF-guarded fetching
# --------------------------------------------------------------------------


class Blocked(Exception):
    pass


def _assert_public(host: str) -> None:
    """Resolve, then check every resolved address. Resolve-then-check, not check-then-resolve."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise Blocked(f"cannot resolve {host}") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (address.is_private or address.is_loopback or address.is_link_local
                or address.is_reserved or address.is_multicast
                or address.is_unspecified):
            raise Blocked(f"{host} resolves to non-public {address}")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def fetch_card(uri: str) -> dict | None:
    """Fetch and parse one agent card. Returns None on any failure."""
    try:
        if uri.startswith("data:"):
            head, _, payload = uri.partition(",")
            raw = (base64.b64decode(payload + "==")
                   if ";base64" in head else urllib.parse.unquote(payload).encode())
            value = json.loads(raw[:MAX_CARD_BYTES])
            return value if isinstance(value, dict) else None
        if uri.startswith("ipfs://"):
            uri = "https://ipfs.io/ipfs/" + uri[7:].lstrip("/")
        if not uri.startswith(("http://", "https://")):
            return None
        host = urllib.parse.urlparse(uri).hostname
        if not host:
            return None
        _assert_public(host)
        request = urllib.request.Request(uri, headers={"user-agent": UA["user-agent"]})
        with _OPENER.open(request, timeout=12) as response:
            value = json.loads(response.read(MAX_CARD_BYTES))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


# --------------------------------------------------------------------------
# Collection
# --------------------------------------------------------------------------


def collect_mints(sample: int) -> list[dict]:
    head = int(rpc("eth_blockNumber", []), 16)
    mints: list[dict] = []
    low = head
    while len(mints) < sample and low > head - 3_000_000:
        high, low = low, low - MAX_LOG_SPAN
        logs = rpc("eth_getLogs", [{
            "fromBlock": hex(low), "toBlock": hex(high),
            "address": ID_REGISTRY, "topics": [TRANSFER, ZERO_TOPIC],
        }])
        if not isinstance(logs, list):
            break
        for entry in logs:
            if len(entry["topics"]) > 3:
                mints.append({
                    "token_id": int(entry["topics"][3], 16),
                    "owner": "0x" + entry["topics"][2][-40:],
                    "block": int(entry["blockNumber"], 16),
                })
    seen, unique = set(), []
    for m in sorted(mints, key=lambda m: -m["block"]):
        if m["token_id"] not in seen:
            seen.add(m["token_id"])
            unique.append(m)
    return unique[:sample]


def attach_timestamps(mints: list[dict]) -> None:
    """Real block timestamps, batched. No interpolation -- unresolved blocks are dropped."""
    blocks = sorted({m["block"] for m in mints})
    times: dict[int, int] = {}
    for i in range(0, len(blocks), 25):
        chunk = blocks[i:i + 25]
        time.sleep(0.35)
        results = rpc_batch([("eth_getBlockByNumber", [hex(b), False]) for b in chunk])
        for block, result in zip(chunk, results):
            if isinstance(result, dict) and result.get("timestamp"):
                times[block] = int(result["timestamp"], 16)
    for m in mints:
        m["timestamp"] = times.get(m["block"])


def attach_uris(mints: list[dict]) -> None:
    for i in range(0, len(mints), 25):
        chunk = mints[i:i + 25]
        time.sleep(0.35)
        results = rpc_batch([
            ("eth_call", [{"to": ID_REGISTRY,
                           "data": "0xc87b56dd" + f"{m['token_id']:064x}"}, "latest"])
            for m in chunk
        ])
        for m, data in zip(chunk, results):
            m["uri"] = None
            if isinstance(data, str) and data != "0x":
                try:
                    raw = bytes.fromhex(data[2:])
                    length = int.from_bytes(raw[32:64], "big")
                    m["uri"] = raw[64:64 + length].decode("utf-8", "replace")
                except Exception:
                    pass


def attach_cards(mints: list[dict]) -> None:
    with ThreadPoolExecutor(8) as pool:
        cards = list(pool.map(lambda m: fetch_card(m["uri"]) if m.get("uri") else None,
                              mints))
    # One extra hop: some cards are {"v":2,"url":...} pointers.
    def hop(pair):
        m, card = pair
        if isinstance(card, dict) and set(card) <= {"v", "url", "payload_sha256"}:
            target = card.get("url")
            if isinstance(target, str):
                return fetch_card(target) or card
        return card
    with ThreadPoolExecutor(8) as pool:
        cards = list(pool.map(hop, zip(mints, cards)))
    for m, card in zip(mints, cards):
        m["card"] = card if isinstance(card, dict) else None


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------


def build_corpus(mints: list[dict]):
    """Each registration becomes one post authored by the identity it claims."""
    from attentiophages.metrics import Corpus, Post

    posts = []
    for m in mints:
        card = m.get("card") or {}
        name = card.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        if m.get("timestamp") is None:
            continue
        description = card.get("description")
        posts.append(Post(
            id=str(m["token_id"]),
            author=name.strip(),
            timestamp=float(m["timestamp"]),
            text=description if isinstance(description, str) else "",
        ))
    return Corpus(posts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sample", type=int, default=800)
    parser.add_argument("--out", default="tmp/erc8004_audit.json")
    parser.add_argument("--load", action="store_true",
                        help="reuse previously fetched data instead of hitting the RPC")
    args = parser.parse_args()

    if args.load and Path(args.out).exists():
        mints = json.load(open(args.out))
        print(f"loaded {len(mints)} cached registrations from {args.out}")
        named = [m for m in mints if m.get("card") and m["card"].get("name")]
        return analyse(mints, named)

    print(f"collecting up to {args.sample} registrations …")
    mints = collect_mints(args.sample)
    print(f"  {len(mints)} mints, blocks {mints[-1]['block']:,}–{mints[0]['block']:,}")
    attach_timestamps(mints)
    attach_uris(mints)
    print(f"  {sum(1 for m in mints if m.get('uri'))} tokenURIs resolved")
    attach_cards(mints)
    named = [m for m in mints if m.get("card") and m["card"].get("name")]
    print(f"  {sum(1 for m in mints if m.get('card'))} cards fetched, "
          f"{len(named)} carry a name")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as handle:
        json.dump(mints, handle, indent=1)
    print(f"  cached -> {args.out}")

    return analyse(mints, named)


def analyse(mints: list[dict], named: list[dict]) -> int:
    corpus = build_corpus(mints)
    print(f"\ncorpus: {len(corpus)} registrations, {len(corpus.authors)} distinct names")

    # ---- baseline: group by owner address -------------------------------
    by_owner = defaultdict(list)
    for m in named:
        by_owner[m["owner"]].append(m["card"]["name"].strip())
    baseline = {o: names for o, names in by_owner.items() if len(names) >= 3}
    covered_baseline = {n for names in baseline.values() for n in names}
    print(f"\nBASELINE  group by owner address (>=3 registrations)")
    print(f"  {len(baseline)} owner groups covering "
          f"{len(covered_baseline)} distinct names")
    for owner, names in sorted(baseline.items(), key=lambda kv: -len(kv[1]))[:5]:
        top = Counter(names).most_common(2)
        print(f"    {owner[:12]}…  {len(names):>4} regs  {top}")

    # ---- detector -------------------------------------------------------
    from attentiophages.metrics import (
        detect_coalitions, isolated_clusters, shared_identity_clusters,
    )

    coalitions = detect_coalitions(corpus, min_size=3)
    print(f"\nDETECTOR  detect_coalitions (name stem + text + timing)")
    print(f"  {len(coalitions)} clusters found")
    for c in coalitions[:10]:
        owners = {m["owner"] for m in named
                  if m["card"]["name"].strip() in c.members}
        print(f"    {c.stem!r:<34} size={c.size:<3} "
              f"text={c.text_similarity:.2f} timing={c.timing_similarity:.2f} "
              f"owners={len(owners)}")

    detected = {n for c in coalitions for n in c.members}
    overlap = detected & covered_baseline
    print(f"\n  detector names: {len(detected)}   baseline names: {len(covered_baseline)}"
          f"   overlap: {len(overlap)}")
    print(f"  found by detector but NOT by owner-grouping: "
          f"{sorted(detected - covered_baseline)[:8]}")

    # one label, many independent minters -- invisible to both methods above
    shared = shared_identity_clusters(
        ((m["card"]["name"], m["owner"]) for m in named), min_controllers=3)
    print(f"\nTHIRD SIGNAL  shared_identity_clusters (one name, many minters)")
    print(f"  {len(shared)} labels claimed by >=3 distinct owners")
    for s_ in shared[:8]:
        print(f"    {s_.label[:40]:<42} {s_.claims:>4} regs across "
              f"{s_.controller_count:>3} owners")
    shared_names = {s_.label for s_ in shared}
    print(f"  caught by neither baseline nor detector: "
          f"{len(shared_names - covered_baseline - detected)}")

    print(f"\n  isolated_clusters: {len(isolated_clusters(corpus))} "
          f"(a registry has no endorsement edges, so this is expected to be 0)")

    # ---- is the reputation layer used at all? ---------------------------
    head = int(rpc("eth_blockNumber", []), 16)
    rep_logs = rpc("eth_getLogs", [{
        "fromBlock": hex(head - MAX_LOG_SPAN), "toBlock": hex(head),
        "address": REP_REGISTRY,
    }])
    count = len(rep_logs) if isinstance(rep_logs, list) else "error"
    print(f"\nReputationRegistry events in the last {MAX_LOG_SPAN:,} blocks: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
