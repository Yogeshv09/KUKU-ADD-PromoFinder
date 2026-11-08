"""Stage 2 (optional, AI): an LLM re-scores the rule shortlist and may nudge the cut points.

Guardrails kept in code, not in the prompt:
  * the model never writes timestamps; it picks line IDs that exist in the context it was shown
  * new cut points are snapped to legal shot boundaries and must keep the promo 20-60 s
  * anything invalid -> the rule-based cut is kept and the issue is logged
"""
from __future__ import annotations

from .candidates import Promo, Segment, WEIGHTS, MIN_LEN, MAX_LEN, EpisodeIndex
from .llm import LLM
from .parser import fmt

SYSTEM = """You are a senior performance-marketing editor for vertical microdrama apps (ReelShort, DramaBox style).
You judge candidate PROMO CLIPS cut from a screenplay. A great promo:
 1. HOOK: the first 3 seconds alone make a scrolling viewer stop (slap, reveal, shocking line, danger).
 2. CLIFFHANGER: it ends on an unresolved moment so the viewer must know what happens next. Ending right
    before an answer/reaction is ideal; ending on a resolution, a hug or a calm line is bad.
 3. STANDALONE: a stranger who never saw the show understands who is in conflict and why it matters.
Score harshly and use the full 0-10 range; most clips are 4-7. Return ONLY JSON."""

USER_TMPL = """SHOW CONTEXT (for you only, viewers never see this): Episode {ep} logline: {logline}

Lines marked IN are inside the proposed clip; OUT lines are nearby context you may extend into.
Format: [line_id] IN|OUT mm:ss.ss-mm:ss.ss TYPE SPEAKER (delivery): text
{lines}

Proposed clip: {segs} (total {dur:.1f}s){stitch_note}

Return JSON with keys:
 "hook_score" 0-10, "cliff_score" 0-10, "standalone_score" 0-10,
 "start_id": line_id the clip should start on (any IN/OUT id; keep the proposal if it is already right),
 "end_id": line_id the clip should end after,
 "hook": what the viewer sees/hears in the first 3 seconds (<= 15 words),
 "cliffhanger": the unresolved moment it ends on (<= 15 words),
 "why": one line on why this promo works (or why it does not),
 "issues": list of short problems (e.g. "needs backstory", "ends on resolution", "slow first 3s")."""


def render_lines(events, inside: list[tuple[int, float, float]]):
    out = []
    for e in events:
        tag = "IN " if any(e.ep == ep and e.start >= a - 0.2 and e.end <= b + 0.3 for ep, a, b in inside) else "OUT"
        who = f"{e.speaker} ({', '.join(e.delivery)})" if e.kind == "dialogue" else ""
        out.append(f"[{e.uid}] {tag} {fmt(e.start)}-{fmt(e.end)} {e.kind.upper()} {who}: {e.text}")
    return "\n".join(out)


def context_events(p: Promo, idx: dict[int, EpisodeIndex], pad: float = 10.0):
    evs = []
    for s in p.segments:
        ix = idx[s.ep]
        evs += [e for e in ix.events if s.start - pad <= e.start <= s.end + pad]
    seen, out = set(), []
    for e in evs:
        if e.uid not in seen:
            seen.add(e.uid)
            out.append(e)
    return out


def _clamp(x):
    try:
        return max(0.0, min(10.0, float(x)))
    except (TypeError, ValueError):
        return None


def judge(promos: list[Promo], idx: dict[int, EpisodeIndex], eps_by_num: dict, llm: LLM, top: int = 40,
          blend: float = 0.6, log=print):
    if not llm.enabled:
        return promos
    for n, p in enumerate(promos[:top]):
        ctx = context_events(p, idx)
        inside = [(s.ep, s.start, s.end) for s in p.segments]
        segs = " + ".join(f"E{s.ep} {fmt(s.start)}-{fmt(s.end)}" for s in p.segments)
        stitched = len(p.segments) > 1
        msg = USER_TMPL.format(ep=p.first_ep, logline=eps_by_num[p.first_ep].logline,
                               lines=render_lines(ctx, inside), segs=segs, dur=p.duration,
                               stitch_note=" — STITCHED from two moments; judge only, keep start_id/end_id as proposed."
                               if stitched else "")
        try:
            r = llm.chat_json(SYSTEM, msg)
        except Exception as ex:
            log(f"  [judge] promo {n + 1}: LLM failed ({ex}); keeping rule score")
            continue
        h, c, st = _clamp(r.get("hook_score")), _clamp(r.get("cliff_score")), _clamp(r.get("standalone_score"))
        notes = []
        if None in (h, c, st):
            notes.append("LLM returned invalid scores; ignored")
            p.llm = {"raw": r, "notes": notes}
            continue
        # optional boundary adjustment (single-segment promos only)
        if not stitched:
            new = _adjust(p, r.get("start_id"), r.get("end_id"), ctx, idx)
            if isinstance(new, str):
                notes.append(new)
            elif new is not None:
                notes.append(f"cut moved {segs} -> E{new.ep} {fmt(new.start)}-{fmt(new.end)}")
                p.segments = [new]
                p.events = idx[new.ep].window_events(new.start, new.end)
        llm_total = (WEIGHTS["hook"] * h + WEIGHTS["cliff"] * c + WEIGHTS["body"] * p.scores["body"]
                     + WEIGHTS["standalone"] * st)
        p.scores.update({"llm_hook": h, "llm_cliff": c, "llm_standalone": st, "llm_total": round(llm_total, 3),
                         "total": round((1 - blend) * p.scores["rule_total"] + blend * llm_total, 3)})
        p.llm = {"model": llm.describe(), "hook": r.get("hook"), "cliffhanger": r.get("cliffhanger"),
                 "why": r.get("why"), "issues": r.get("issues") or [], "notes": notes}
        log(f"  [judge] {n + 1}/{min(top, len(promos))} {segs}: H{h:.0f} C{c:.0f} S{st:.0f}")
    promos.sort(key=lambda q: -q.total)
    return promos


def _adjust(p: Promo, sid, eid, ctx, idx) -> Segment | str | None:
    seg = p.segments[0]
    if not sid and not eid:
        return None
    by_id = {e.uid: e for e in ctx}
    if (sid and sid not in by_id) or (eid and eid not in by_id):
        return f"LLM referenced unknown line id ({sid}, {eid}); kept rule cut"
    ix = idx[seg.ep]
    start = seg.start
    if sid:
        t = by_id[sid].start
        legal = [s for s in ix.starts if s <= t + 0.05]
        start = max(legal) if legal else seg.start
    end = seg.end
    if eid:
        t = by_id[eid].end
        legal = [e for e in ix.ends if e >= t - 0.05]
        end = min(legal) if legal else seg.end
    if abs(start - seg.start) < 0.05 and abs(end - seg.end) < 0.05:
        return None
    if not (MIN_LEN <= end - start <= MAX_LEN):
        return f"LLM cut {fmt(start)}-{fmt(end)} is {end - start:.1f}s (outside 20-60s); kept rule cut"
    return Segment(seg.ep, start, end)
