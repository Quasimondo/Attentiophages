"""Run the v2 metrics on the Moltbook corpus they were written for.

``attentiophages.metrics`` was written to generalise findings that
``docs/03-findings-moltbook.md`` made by eye in v1. Until this tool existed,
nothing in the repository loaded the Moltbook database into a ``Corpus``, so
the v2 code had never touched the data its findings describe. This does that,
read-only, and reports what the detectors actually say:

* ``detect_coalitions``: does the ``coalition_node`` cluster stand out from the
  hundreds of innocent name stems (``MoltyBot42``, ``CodePal174``) on the two
  corroborating signals, or only on its size?
* ``credibility_divergence``: where do the three curator accounts of docs/03
  §3 land, and how many agents get a number at all?
* ``endorsement_concentration`` / ``isolated_clusters``: what the amplification
  graph looks like, and how thin it is.

Quality is the pipeline's ``substance`` score (Qwen 2.5 7B, prompt v1.2);
see ``docs/11-rater-agreement.md`` for how far to trust it. Amplification
edges come from captured comments (a comment replies to a post's author) and
from ``@name`` mentions in post text that resolve to a known author.

    python3 tools/moltbook_metrics.py --db /path/to/moltbook.db
    python3 tools/moltbook_metrics.py --load      # re-print the saved result
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from attentiophages.metrics import (  # noqa: E402
    Corpus,
    Post,
    Unavailable,
    agent_quality,
    amplification_edges,
    credibility_divergence,
    detect_coalitions,
    endorsement_concentration,
    isolated_clusters,
    network_impact,
)

RATER, PROMPT = "qwen2.5:7b", "v1.2"
CURATORS = ("TokenWright", "SonnetSpark", "Ecdysis")
COALITION = "coalition_node"
MENTION = re.compile(r"(?<![\w/.:-])@([A-Za-z0-9_\-]{2,40})")
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "tmp" / "moltbook_metrics.json"


def _ts(iso: str | None) -> float:
    if not iso:
        return 0.0
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def load_corpus(db: Path) -> tuple[Corpus, dict]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT p.id, p.author_name, p.created_at, p.title, p.content, s.score, sp.score "
        "FROM posts p "
        "LEFT JOIN content_scores s ON s.content_id=p.id AND s.content_type='post' "
        " AND s.analysis_type='substance' AND s.model_name=? AND s.prompt_version=? "
        "LEFT JOIN content_scores sp ON sp.content_id=p.id AND sp.content_type='post' "
        " AND sp.analysis_type='spam' AND sp.model_name=? AND sp.prompt_version=? "
        "WHERE p.author_name IS NOT NULL", (RATER, PROMPT, RATER, PROMPT)).fetchall()
    authors = {r[1] for r in rows}
    posts: list[Post] = []
    mention_hits = 0
    for pid, author, created, title, content, substance, spam in rows:
        text = (title or "") + "\n\n" + (content or "")
        mentions = tuple(sorted({m for m in MENTION.findall(text) if m in authors and m != author}))
        mention_hits += len(mentions)
        scores = {}
        if substance is not None:
            scores["quality"] = float(substance)
        if spam is not None:
            scores["spam"] = float(spam)
        posts.append(Post(id=pid, author=author, timestamp=_ts(created), text=text,
                          mentions=mentions, scores=scores))
    comments = conn.execute(
        "SELECT id, post_id, author_name, created_at, content FROM comments "
        "WHERE author_name IS NOT NULL").fetchall()
    for cid, post_id, author, created, content in comments:
        posts.append(Post(id=f"c:{cid}", author=author, timestamp=_ts(created),
                          text=content or "", parent_id=post_id))
    conn.close()
    stats = {"posts": len(rows), "scored_substance": sum(1 for r in rows if r[5] is not None),
             "comments": len(comments), "authors": len(authors),
             "resolved_mentions": mention_hits}
    return Corpus(posts), stats


def analyse(corpus: Corpus, stats: dict) -> dict:
    out: dict = {"corpus": stats}

    # -- coalitions: the coalition_node stem against every other stem ---------
    coalitions = detect_coalitions(corpus, min_size=3)
    out["coalitions_found"] = len(coalitions)
    by_stem = {c.stem: c for c in coalitions}
    target = by_stem.get(COALITION)
    others = [c for c in coalitions if c.stem != COALITION]
    text_rank = sum(1 for c in others if c.text_similarity > target.text_similarity) + 1 if target else None
    time_rank = sum(1 for c in others if c.timing_similarity > target.timing_similarity) + 1 if target else None
    out["coalition_node"] = None if not target else {
        "size": target.size, "text_similarity": target.text_similarity,
        "timing_similarity": target.timing_similarity,
        "text_rank_among_stems": text_rank, "timing_rank_among_stems": time_rank,
        "size_rank_among_stems": sum(1 for c in others if c.size > target.size) + 1,
    }
    out["stem_distribution"] = {
        "text_similarity_median": median(c.text_similarity for c in coalitions),
        "timing_similarity_median": median(c.timing_similarity for c in coalitions),
        "text_similarity_p90": sorted(c.text_similarity for c in coalitions)[int(0.9 * len(coalitions))],
        "timing_similarity_p90": sorted(c.timing_similarity for c in coalitions)[int(0.9 * len(coalitions))],
    }
    out["top_stems_by_size"] = [(c.stem, c.size, round(c.text_similarity, 3), round(c.timing_similarity, 3))
                                for c in coalitions[:12]]
    out["top_stems_by_text_similarity"] = [
        (c.stem, c.size, round(c.text_similarity, 3), round(c.timing_similarity, 3))
        for c in sorted(coalitions, key=lambda c: -c.text_similarity)[:12]]

    # -- amplification graph ----------------------------------------------------
    edges = amplification_edges(corpus)
    out_w = Counter()
    for (src, _), w in edges.items():
        out_w[src] += w
    out["graph"] = {"edges": len(edges), "sources": len(out_w), "targets": len({d for _, d in edges}),
                    "sources_with_out_weight_ge_3": sum(1 for w in out_w.values() if w >= 3)}
    clusters = isolated_clusters(corpus)
    out["isolated_clusters"] = {"count": len(clusters), "largest": len(clusters[0]) if clusters else 0,
                               "members_total": sum(len(c) for c in clusters)}
    conc = endorsement_concentration(corpus)
    out["endorsement_concentration"] = {
        "agents": len(conc),
        "at_1.0_with_out_weight_ge_3": sum(1 for a, v in conc.items() if v >= 0.999 and out_w[a] >= 3),
    }

    # -- quality and credibility divergence -------------------------------------
    quality = agent_quality(corpus)
    impact = network_impact(corpus)
    div = credibility_divergence(corpus)
    numeric = {a: v for a, v in div.items() if not isinstance(v, Unavailable)}
    out["credibility_divergence"] = {
        "agents_with_quality": len(quality),
        "agents_with_a_number": len(numeric),
        "top_positive": [(a, round(v, 3), round(quality[a], 2), round(impact[a].mean, 2), impact[a].out_weight)
                         for a, v in sorted(numeric.items(), key=lambda kv: -kv[1])[:10]],
        "top_negative": [(a, round(v, 3), round(quality[a], 2), round(impact[a].mean, 2), impact[a].out_weight)
                         for a, v in sorted(numeric.items(), key=lambda kv: kv[1])[:5]],
    }
    out["curators"] = {}
    for name in CURATORS:
        v = div.get(name)
        out["curators"][name] = {
            "posts": len(corpus.by_author(name)),
            "quality": round(quality[name], 2) if name in quality else None,
            "out_weight": out_w.get(name, 0.0),
            "targets": sorted({d for (s, d) in edges if s == name}),
            "divergence": round(v, 3) if isinstance(v, float) else (v.reason if v is not None else "not in corpus"),
        }
    who_amplifies_coalition = Counter(s for (s, d) in edges if d.startswith(COALITION))
    out["amplifiers_of_coalition_node"] = who_amplifies_coalition.most_common(10)
    coal_q = [quality[a] for a in quality if a.startswith(COALITION)]
    out["coalition_node_quality"] = {"agents_scored": len(coal_q), "mean": round(mean(coal_q), 2) if coal_q else None,
                                     "corpus_median": round(median(quality.values()), 2)}
    return out


def report(r: dict) -> None:
    c = r["corpus"]
    print(f"corpus: {c['posts']} posts ({c['scored_substance']} with substance), {c['comments']} comments, "
          f"{c['authors']} authors, {c['resolved_mentions']} resolved @mentions")
    print(f"\n== detect_coalitions: {r['coalitions_found']} name stems with >= 3 members")
    cn = r["coalition_node"]
    if cn:
        print(f"  coalition_node: size {cn['size']} (rank {cn['size_rank_among_stems']}), "
              f"text {cn['text_similarity']:.3f} (rank {cn['text_rank_among_stems']}), "
              f"timing {cn['timing_similarity']:.3f} (rank {cn['timing_rank_among_stems']})")
    d = r["stem_distribution"]
    print(f"  all stems: text median {d['text_similarity_median']:.3f} p90 {d['text_similarity_p90']:.3f}; "
          f"timing median {d['timing_similarity_median']:.3f} p90 {d['timing_similarity_p90']:.3f}")
    print("  largest stems (stem, size, text, timing):")
    for row in r["top_stems_by_size"]:
        print("   ", row)
    print("  most text-similar stems:")
    for row in r["top_stems_by_text_similarity"]:
        print("   ", row)
    g = r["graph"]
    print(f"\n== amplification graph: {g['edges']} edges from {g['sources']} sources to {g['targets']} targets; "
          f"{g['sources_with_out_weight_ge_3']} sources with out-weight >= 3")
    ic = r["isolated_clusters"]
    print(f"  isolated clusters: {ic['count']} (largest {ic['largest']}, {ic['members_total']} agents in total)")
    ec = r["endorsement_concentration"]
    print(f"  endorsement concentration: {ec['agents']} agents; {ec['at_1.0_with_out_weight_ge_3']} at 1.0 with >= 3 edges")
    cd = r["credibility_divergence"]
    print(f"\n== credibility_divergence: {cd['agents_with_a_number']} of {cd['agents_with_quality']} scored agents get a number")
    print("  top positive (agent, divergence, quality, impact mean, out weight):")
    for row in cd["top_positive"]:
        print("   ", row)
    print("  top negative:")
    for row in cd["top_negative"]:
        print("   ", row)
    print("\n== the curators of docs/03 §3")
    for name, info in r["curators"].items():
        print(f"  {name}: {info}")
    print(f"  who amplifies coalition_node accounts: {r['amplifiers_of_coalition_node'] or 'nobody in the captured graph'}")
    print(f"  coalition_node quality: {r['coalition_node_quality']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", type=Path)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--load", action="store_true")
    args = ap.parse_args(argv)
    if args.load:
        result = json.loads(args.out.read_text())
    else:
        if not args.db:
            ap.error("--db required")
        corpus, stats = load_corpus(args.db)
        result = analyse(corpus, stats)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=1))
    report(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
