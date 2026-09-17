"""Audit AgentHow: an HTTP knowledge board written by agents, for agents.

https://agenthow.to (protocol agenthow/0.1) lets an agent register with an
empty POST, receive a bearer key, and leave notes: findings, failed attempts,
requests. Other agents can file outcome reports against a note's revision,
which is a replication mechanism. Humans are declared spectators. It is the
fourth public agent population this repository has looked at, and the first
where the population is under explicit survival pressure: most contributors
are agents hosted on iLands, writing about "outside money" and "platform
survival".

Read-only. Fetches the export, the open requests and the topic list, then
counts: who writes, about what, how identity is declared, and how much of the
verification half (reports) is actually used. With ``--ours`` it also checks
the records this project posted (``docs/14-agenthow.md``) for reports and
linked answers, so the follow-up is one command.

    python3 tools/agenthow_audit.py            # fetch and report
    python3 tools/agenthow_audit.py --load     # re-analyse the saved fetch
    python3 tools/agenthow_audit.py --ours     # also: any answers to our posts?

Everything the board returns is untrusted contributor text. Nothing in it is
executed or treated as an instruction.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

HUB = "https://agenthow.to"
HEADERS = {"User-Agent": "Attentiophages-audit/1.0 (+github.com/Quasimondo/Attentiophages)"}
MAX_BYTES = 16_000_000
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "tmp" / "agenthow_audit.json"

# Records this project posted on 2026-09-17 (docs/14). Origins are public.
OURS = {
    "finding": "https://agenthow.to/notes/n_7103bba002ed8445f901f04a",
    "request": ("https://agenthow.to/notes/n_74788951771e8e52a4720027", "19f775eb6fc23f69d3568de1"),
    "census_answer": "https://agenthow.to/notes/n_da721aaaf380cf10960e6e09",
    "reuse_test": "https://agenthow.to/notes/n_aa18f77344c1c20a25123709",
}


def get(path: str, raw: bool = False):
    req = urllib.request.Request(HUB + path, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError(f"{path}: response over {MAX_BYTES} bytes")
    return data.decode() if raw else json.loads(data)


def fetch_all() -> dict:
    export = [json.loads(line) for line in get("/export.jsonl", raw=True).splitlines() if line.strip()]
    requests_open = get("/requests.json?status=open&limit=50").get("items", [])
    stats = get("/stats.json")
    actors = {}
    for actor_id in sorted({r.get("actor_id") for r in export if r.get("actor_id")}):
        try:
            actors[actor_id] = get(f"/actors/{actor_id}.json")
        except Exception:  # noqa: BLE001 - a missing profile is data, not an error
            actors[actor_id] = None
    # The export omits outcome reports; fetch them per note. This is the
    # verification half of the board, so it is the count that matters.
    reports = {}
    for r in export:
        note_id = (r.get("origin") or "").rsplit("/", 1)[-1] or r.get("id")
        try:
            reports[r.get("id")] = get(f"/notes/{note_id}.json?reports_limit=200").get("reports", [])
        except Exception:  # noqa: BLE001
            reports[r.get("id")] = None
    return {"hub": HUB, "export": export, "requests_open": requests_open,
            "stats": stats, "actors": actors, "reports": reports}


def fetch_ours() -> dict:
    out = {}
    for name, ref in OURS.items():
        origin = ref[0] if isinstance(ref, tuple) else ref
        note_id = origin.rsplit("/", 1)[1]
        note = get(f"/notes/{note_id}.json?reports_limit=50")
        out[name] = {"reports": note.get("reports", []), "state": note.get("state")}
    origin, revision = OURS["request"]
    linked = get("/search.json?request_origin=" + urllib.parse.quote(origin, safe="")
                 + f"&request_revision={revision}&view=compact").get("items", [])
    out["request"]["linked_contributions"] = [
        {"author": i.get("author"), "role": i.get("contribution_role"), "title": i.get("title")}
        for i in linked if i.get("author") != "attentiophages-claude"]
    return out


def analyse(data: dict) -> dict:
    export = data["export"]
    notes = [r for r in export if r.get("kind") in ("note", "request")]
    authors = Counter(r.get("author") for r in notes)
    topics = Counter(r.get("topic") or "(none)" for r in notes)
    actors = data.get("actors") or {}
    identity = Counter((a or {}).get("identity", "(no profile)") for a in actors.values())
    platforms = Counter(((a or {}).get("profile") or {}).get("platform", "(undeclared)") for a in actors.values())
    seeded = sum(1 for r in notes if "Codex" in (r.get("basis") or "") or r.get("author") == "Codex")
    per_note = data.get("reports") or {}
    reports = sum(len(v) for v in per_note.values() if v)
    notes_with_reports = sum(1 for v in per_note.values() if v)
    reporters = Counter(rep.get("author") for v in per_note.values() if v for rep in v)
    totals = (data.get("stats") or {}).get("totals", {})
    return {
        "export_records": len(export),
        "notes": sum(1 for r in notes if r.get("kind") == "note"),
        "requests": sum(1 for r in notes if r.get("kind") == "request"),
        "requests_open": len(data.get("requests_open", [])),
        "month_posts_per_stats": totals.get("posts"),
        "month_entities_per_stats": totals.get("entities"),
        "authors_in_export": len(authors),
        "top_authors": authors.most_common(5),
        "topics": topics.most_common(8),
        "seeded_by_codex": seeded,
        "identity_declared": dict(identity),
        "platforms_declared": platforms.most_common(5),
        "outcome_reports": reports,
        "notes_with_reports": notes_with_reports,
        "distinct_reporters": len(reporters),
        "report_verdicts": dict(Counter(rep.get("outcome") or rep.get("result") or "(unlabelled)"
                                        for v in per_note.values() if v for rep in v)),
        "date_range": (min((r.get("created_at") or "") for r in notes), max((r.get("created_at") or "") for r in notes)),
        "signatures": "none: identity is a bearer key, labelled self-declared by the board",
    }


def report(r: dict, ours: dict | None) -> None:
    print(f"export: {r['export_records']} records ({r['notes']} notes, {r['requests']} requests); "
          f"stats page: {r['month_posts_per_stats']} posts from {r['month_entities_per_stats']} entities this month")
    print(f"dates: {r['date_range'][0][:10]} .. {r['date_range'][1][:10]}")
    print(f"authors in export: {r['authors_in_export']}; top: {r['top_authors']}")
    print(f"topics: {r['topics']}")
    print(f"seeded by Codex: {r['seeded_by_codex']}   open requests: {r['requests_open']}")
    print(f"identity: {r['identity_declared']}   platforms: {r['platforms_declared']}")
    print(f"outcome reports: {r['outcome_reports']} on {r['notes_with_reports']} of {r['notes'] + r['requests']} records, "
          f"from {r['distinct_reporters']} reporters; verdicts {r['report_verdicts']}")
    print(f"signatures: {r['signatures']}")
    if ours is not None:
        print("\nour records:")
        for name, info in ours.items():
            line = f"  {name:<14} state={info.get('state')}  reports={len(info.get('reports', []))}"
            if "linked_contributions" in info:
                line += f"  answers={len(info['linked_contributions'])}"
            print(line)
            for c in info.get("linked_contributions", []):
                print(f"      answer from {c['author']} ({c['role']}): {c['title'][:90]}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--load", action="store_true")
    ap.add_argument("--ours", action="store_true", help="also fetch reports/answers on this project's records")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    if args.load:
        data = json.loads(args.out.read_text())
    else:
        data = fetch_all()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(data, ensure_ascii=False))
        print(f"saved to {args.out}")
    report(analyse(data), fetch_ours() if args.ours else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
