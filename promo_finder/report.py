"""Turn scored promos into editor-facing outputs: ranked list, posting plan, transcripts."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from .candidates import Promo
from .parser import fmt
from . import signals as S

HOOK_PHRASE = {"violence": "physical violence", "danger": "life-or-death danger", "humiliation": "public humiliation",
               "reveal": "a secret / status reveal", "romance": "forbidden romance", "confront": "a direct confrontation"}
CLIFF_PHRASE = {"cuts-before-answer": "cuts right before the answer", "question": "an unanswered question",
                "threat": "an open threat", "interrupted": "a line cut off mid-sentence",
                "entrance": "someone arriving or watching", "reveal": "a half-revealed secret",
                "danger": "danger still in motion", "reaction": "a frozen shock reaction", "decision": "a decision left hanging",
                "marker": "a musical sting / shock beat"}
CATEGORY_ORDER = ["violence", "danger", "reveal", "humiliation", "romance", "confront"]


def _ev_text(e, n=140):
    if e is None:
        return ""
    t = e.text if len(e.text) <= n else e.text[: n - 1] + "…"
    if e.kind == "dialogue":
        d = f" ({', '.join(e.delivery[:2])})" if e.delivery else ""
        return f'{e.speaker.title()}{d}: "{t}"'
    return f"[{e.kind}] {t}"


def category(p: Promo) -> str:
    for c in CATEGORY_ORDER:
        if c in p.tags.get("hook", []):
            return c
    return "drama"


def describe(p: Promo) -> dict:
    if p.llm and p.llm.get("hook"):
        return {"hook": p.llm["hook"], "cliffhanger": p.llm.get("cliffhanger") or "", "why": p.llm.get("why") or "",
                "source": p.llm.get("model")}
    dl = [e for e in p.events if e.kind == "dialogue"]
    last_line = dl[-1] if dl else None
    cliff = _ev_text(last_line)
    if p.cliff_ev is not None and p.cliff_ev is not last_line and p.cliff_ev.kind != "dialogue":
        cliff = (cliff + " → " if cliff else "") + _ev_text(p.cliff_ev, 110)
    htags = [HOOK_PHRASE[t] for t in CATEGORY_ORDER if t in p.tags.get("hook", [])][:2]
    ctags = [CLIFF_PHRASE[t] for t in CLIFF_PHRASE if t in p.tags.get("cliff", [])][:2]
    back = sum(S.backstory_refs(e.text) for e in dl)
    why = (f"Opens on {' + '.join(htags) or 'a high-emotion line'}; ends on {' and '.join(ctags) or 'an open beat'}; "
           f"{p.tags.get('speakers', 0)} speaker{'s' if p.tags.get('speakers', 0) != 1 else ''}"
           + (", no backstory needed." if back == 0 else f", but {back} backstory reference(s) may confuse new viewers."))
    if len(p.segments) > 1:
        why += " Stitched: skips a slower middle."
    return {"hook": _ev_text(p.hook_ev), "cliffhanger": cliff, "why": why, "source": "rules"}


def transcript(p: Promo, include_camera=False):
    out = []
    for s in p.segments:
        for e in p.events:
            if e.ep == s.ep and e.start >= s.start - 0.2 and e.end <= s.end + 0.3:
                if e.kind == "camera" and not include_camera:
                    continue
                out.append(f"E{e.ep} {fmt(e.start)} {_ev_text(e, 220)}")
    return out


def rank_for_posting(promos: list[Promo], n_eps: int, slate=10):
    """Posting order = quality x funnel position. Early-episode promos land new viewers at the start of
    the show and spoil less, so they get up to a 25% boost over episode-50 promos."""
    max_ep = max(n_eps, 2)
    for p in promos:
        p.scores["post_score"] = round(p.total * (1 - 0.25 * (p.first_ep - 1) / (max_ep - 1)), 3)
    order = sorted(promos, key=lambda p: -p.scores["post_score"])
    chosen, eps, cats = [], set(), Counter()
    for p in order:  # diversity: <=1 per episode, <=3 per hook category
        cat = category(p)
        if p.first_ep in eps or cats[cat] >= 3:
            continue
        chosen.append(p)
        eps.add(p.first_ep)
        cats[cat] += 1
        if len(chosen) == slate:
            break
    return order, chosen


def to_records(promos: list[Promo], slate: list[Promo]):
    slate_pos = {id(p): i + 1 for i, p in enumerate(slate)}
    recs = []
    for i, p in enumerate(promos, 1):
        d = describe(p)
        recs.append({
            "rank": i, "post_first_slot": slate_pos.get(id(p)), "type": p.tags.get("type"),
            "category": category(p), "episodes": sorted({s.ep for s in p.segments}),
            "segments": [s.to_dict() for s in p.segments], "duration_s": round(p.duration, 2),
            "hook": d["hook"], "cliffhanger": d["cliffhanger"], "why": d["why"], "described_by": d["source"],
            "scores": p.scores, "signals": {"hook": p.tags.get("hook"), "cliff": p.tags.get("cliff")},
            "llm_issues": (p.llm or {}).get("issues", []), "llm_notes": (p.llm or {}).get("notes", []),
            "transcript": transcript(p),
        })
    return recs


def write_outputs(out: Path, recs: list[dict], slate: list[Promo], meta: dict):
    out.mkdir(parents=True, exist_ok=True)
    (out / "promos.json").write_text(json.dumps({"meta": meta, "promos": recs}, indent=1, ensure_ascii=False))
    with open(out / "promos.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "post_first_slot", "type", "category", "segments", "duration_s", "hook", "cliffhanger",
                    "why", "total", "hook_score", "cliff_score", "body_score", "standalone_score", "post_score"])
        for r in recs:
            segs = " + ".join(f"E{s['episode']} {s['start']}-{s['end']}" for s in r["segments"])
            sc = r["scores"]
            w.writerow([r["rank"], r["post_first_slot"] or "", r["type"], r["category"], segs, r["duration_s"],
                        r["hook"], r["cliffhanger"], r["why"], sc["total"], sc.get("llm_hook", sc["hook"]),
                        sc.get("llm_cliff", sc["cliff"]), sc["body"], sc.get("llm_standalone", sc["standalone"]),
                        sc["post_score"]])
    # human review sheet: editors fill the blank columns -> precision@k for the next iteration
    with open(out / "review_sheet.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "segments", "hook", "cliffhanger", "hook_ok(y/n)", "cliff_ok(y/n)",
                    "standalone_ok(y/n)", "would_post(y/n)", "better_start", "better_end", "notes"])
        for r in recs:
            segs = " + ".join(f"E{s['episode']} {s['start']}-{s['end']}" for s in r["segments"])
            w.writerow([r["rank"], segs, r["hook"], r["cliffhanger"], "", "", "", "", "", "", ""])

    L = [f"# Promo candidates — {meta['show']}", "",
         f"Model: `{meta['model']}` · episodes: {meta['episodes']} · promos: {len(recs)} · "
         f"generated {meta['generated_at']}", "", "## Post these first", ""]
    rec_by_rank = {r["rank"]: r for r in recs}
    slate_recs = sorted((r for r in recs if r["post_first_slot"]), key=lambda r: r["post_first_slot"])
    for r in slate_recs:
        segs = " + ".join(f"E{s['episode']} {s['start']}–{s['end']}" for s in r["segments"])
        L.append(f"{r['post_first_slot']}. **{segs}** ({r['duration_s']:.0f}s, {r['category']}) — {r['why']}")
    L += ["", "## All promos (ranked by quality)", ""]
    for r in recs:
        segs = " + ".join(f"Ep {s['episode']} {s['start']}–{s['end']}" for s in r["segments"])
        sc = r["scores"]
        L += [f"### #{r['rank']} · {segs} · {r['duration_s']:.1f}s · {r['type']}",
              f"- **Hook:** {r['hook']}", f"- **Cliffhanger:** {r['cliffhanger']}", f"- **Why:** {r['why']}",
              f"- Scores: total {sc['total']:.2f} | hook {sc.get('llm_hook', sc['hook'])} | "
              f"cliff {sc.get('llm_cliff', sc['cliff'])} | standalone {sc.get('llm_standalone', sc['standalone'])} | "
              f"post {sc['post_score']:.2f}"]
        if r["llm_issues"]:
            L.append(f"- LLM flagged: {', '.join(map(str, r['llm_issues']))}")
        L.append("<details><summary>Clip transcript</summary>\n")
        L += [f"    {t}" for t in r["transcript"]]
        L += ["</details>", ""]
    (out / "promos_report.md").write_text("\n".join(L), encoding="utf-8")
    del rec_by_rank
