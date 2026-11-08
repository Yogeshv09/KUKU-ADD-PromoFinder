"""Stage 1 (rules): enumerate every legal promo window, score it, and keep a diverse shortlist.

Legal cut points = camera-shot boundaries that do not fall inside a line of dialogue, so a
promo never cuts mid-shot or mid-sentence. Scores are 0-10 per criterion.
"""
from __future__ import annotations

import bisect
import math
from collections import Counter
from dataclasses import dataclass, field

from .parser import Episode, Event, fmt
from . import signals as S

MIN_LEN, MAX_LEN = 20.0, 60.0
HOOK_WIN, CLIFF_WIN = 3.0, 4.5
WEIGHTS = {"hook": 0.35, "cliff": 0.40, "body": 0.12, "standalone": 0.13}
STITCH_PENALTY = 0.8


def sat(x: float, k: float) -> float:
    return 10.0 * (1.0 - math.exp(-max(x, 0.0) / k))


@dataclass
class Segment:
    ep: int
    start: float
    end: float

    @property
    def dur(self):
        return self.end - self.start

    def to_dict(self):
        return {"episode": self.ep, "start": fmt(self.start), "end": fmt(self.end),
                "start_s": round(self.start, 2), "end_s": round(self.end, 2), "duration_s": round(self.dur, 2)}


@dataclass
class Promo:
    segments: list[Segment]
    scores: dict
    hook_ev: Event | None = None
    cliff_ev: Event | None = None
    tags: dict = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    llm: dict | None = None

    @property
    def duration(self):
        return sum(s.dur for s in self.segments)

    @property
    def total(self):
        return self.scores["total"]

    @property
    def first_ep(self):
        return self.segments[0].ep


class EpisodeIndex:
    """Precomputes cut points and per-cut-point hook/cliff scores for one episode."""

    def __init__(self, ep: Episode, protagonist: str, use_markers: bool = True):
        self.ep, self.protagonist, self.use_markers = ep, protagonist, use_markers
        self.events = ep.events
        self._starts = [e.start for e in ep.events]
        self._wcache = {}
        self.dlg = [e for e in ep.events if e.kind == "dialogue"]
        cams = [e for e in ep.events if e.kind == "camera"] or ep.events
        starts = {round(e.start, 2) for e in cams} | {0.0}
        ends = {round(e.end, 2) for e in cams} | {round(ep.duration, 2)}
        self.starts = sorted(t for t in starts if self._clean(t) and not self._splits_sentence(t))
        self.ends = sorted(t for t in ends if self._clean(t))
        self.hook_at = {t: self._hook(t) for t in self.starts}
        self.cliff_at = {t: self._cliff(t) for t in self.ends}

    def _clean(self, t: float, tol: float = 0.15) -> bool:
        return not any(d.start + tol < t < d.end - tol for d in self.dlg)

    def _splits_sentence(self, t: float) -> bool:
        """True if t falls between the two halves of a line the script splits with '...' """
        nxt = next((d for d in self.dlg if d.start >= t - 0.15), None)
        return bool(nxt and nxt.start - t < 3.0 and nxt.text.lstrip().startswith(("...", "…")))

    def _hook(self, t):
        evs = [e for e in self.events if t - 0.2 <= e.start < t + HOOK_WIN]
        scored = sorted(((S.hook_signal(e), e) for e in evs), key=lambda x: -x[0][0])
        if not scored:
            return 0.0, None, []
        raw = scored[0][0][0] + 0.35 * sum(max(s[0][0], 0) for s in scored[1:])
        if not any(e.kind == "dialogue" for e in evs) and scored[0][0][0] < 2:
            raw -= 0.8  # nothing said and nothing striking happens: easy to scroll past
        tags = sorted({t for (sc, tg), _ in scored[:2] for t in tg})
        return sat(raw, 4.0), scored[0][1], tags

    def _cliff(self, t):
        evs = [e for e in self.events if t - CLIFF_WIN < e.end <= t + 0.2]
        if not evs:
            return 0.0, None, []
        last_d = max((e for e in self.events if e.kind == "dialogue" and e.end <= t + 0.2),
                     key=lambda e: e.end, default=None)
        raw, best, best_s, tags = 0.0, None, -1e9, set()
        for e in evs:
            s, tg = S.cliff_signal(e, self.use_markers)
            w = 1.0 if (e is last_d or e.kind != "dialogue") else 0.5
            raw += w * s if s > 0 else s
            tags |= set(tg)
            if s * w > best_s:
                best, best_s = e, s * w
        if last_d is not None:
            nxt = next((d for d in self.dlg if d.start >= t - 0.05), None)
            # cutting right before the reply/answer = textbook cliffhanger
            if nxt and nxt.start - t < 2.5 and "?" in last_d.text:
                raw += 1.0
                tags.add("cuts-before-answer")
            prev = [d for d in self.dlg if d.end <= last_d.start + 0.05]
            if prev and "?" in prev[-1].text and "?" not in last_d.text and prev[-1].speaker != last_d.speaker \
                    and last_d.start - prev[-1].end < 3.0:
                raw -= 1.5  # the clip shows the answer: the question is resolved on screen
                tags.add("ends-on-answer")
            if t - last_d.end > 4.0 and not tags & {"marker", "reaction", "danger", "entrance"}:
                raw -= 0.8  # clip trails off in silence
            if last_d in evs and (best is None or best_s < 1.0):
                best = last_d
        return sat(raw, 4.0), best, sorted(tags)

    def window_events(self, a, b):
        key = (a, b)
        if key not in self._wcache:
            i = bisect.bisect_left(self._starts, a - 0.2)
            j = bisect.bisect_right(self._starts, b)
            self._wcache[key] = [e for e in self.events[i:j] if e.end <= b + 0.3]
        return self._wcache[key]


def body_and_standalone(evs: list[Event], dur: float, protagonist: str):
    dl = [e for e in evs if e.kind == "dialogue"]
    inten = sum(S.intensity(e) for e in evs)
    body = sat(inten / max(dur, 1) * 10, 12.0)
    if len(dl) < 3:
        body *= 0.6  # promos live on dialogue
    speakers = Counter(e.speaker for e in dl)
    st = 8.0
    st -= 1.2 * min(sum(S.backstory_refs(e.text) for e in dl), 3)
    st -= 1.0 * max(len(speakers) - 3, 0)
    if dl and S.CONTEXT_OPENERS.match(dl[0].text):
        st -= 2.0
    if protagonist in speakers:
        st += 1.0
    if dl and sum(1 for e in dl if e.voice) / len(dl) > 0.4:
        st -= 1.0
    return body, max(0.0, min(10.0, st)), len(speakers)


def dur_penalty(d):
    return 0.0 if 25 <= d <= 45 else 0.05 * (25 - d if d < 25 else d - 45)


def score(hook, cliff, body, stand, dur, stitched=False):
    tot = (WEIGHTS["hook"] * hook + WEIGHTS["cliff"] * cliff + WEIGHTS["body"] * body
           + WEIGHTS["standalone"] * stand - dur_penalty(dur) - (STITCH_PENALTY if stitched else 0))
    return {"hook": round(hook, 2), "cliff": round(cliff, 2), "body": round(body, 2),
            "standalone": round(stand, 2), "rule_total": round(tot, 3), "total": round(tot, 3)}


def single_windows(ix: EpisodeIndex):
    out = []
    for s in ix.starts:
        h, hev, htags = ix.hook_at[s]
        if h < 2.0:
            continue
        for e in ix.ends:
            d = e - s
            if d < MIN_LEN or d > MAX_LEN:
                continue
            c, cev, ctags = ix.cliff_at[e]
            evs = ix.window_events(s, e)
            b, st, nsp = body_and_standalone(evs, d, ix.protagonist)
            sc = score(h, c, b, st, d)
            out.append(Promo([Segment(ix.ep.ep, s, e)], sc, hev, cev,
                             {"hook": htags, "cliff": ctags, "speakers": nsp, "type": "continuous"}, evs))
    return out


def stitched_windows(ix: EpisodeIndex, nxt: EpisodeIndex | None, k: int = 6):
    """Hook moment + later cliff moment, skipping a slow middle (same or next episode)."""
    out = []
    hooks = sorted(ix.starts, key=lambda t: -ix.hook_at[t][0])[:k]
    pools = [(ix, 4.0)] + ([(nxt, 0.0)] if nxt else [])
    for s1 in hooks:
        h, hev, htags = ix.hook_at[s1]
        for e1 in ix.ends:
            if not (6 <= e1 - s1 <= 20):
                continue
            for jx, gap in pools:
                cliffs = sorted(jx.ends, key=lambda t: -jx.cliff_at[t][0])[:k]
                for e2 in cliffs:
                    for s2 in jx.starts:
                        if jx is ix and s2 < e1 + gap:
                            continue
                        d2 = e2 - s2
                        tot = (e1 - s1) + d2
                        if not (10 <= d2 <= 40) or not (MIN_LEN <= tot <= MAX_LEN):
                            continue
                        c, cev, ctags = jx.cliff_at[e2]
                        evs = ix.window_events(s1, e1) + jx.window_events(s2, e2)
                        b, st, nsp = body_and_standalone(evs, tot, ix.protagonist)
                        sc = score(h, c, b, st - 0.5, tot, stitched=True)
                        out.append(Promo([Segment(ix.ep.ep, s1, e1), Segment(jx.ep.ep, s2, e2)], sc, hev, cev,
                                         {"hook": htags, "cliff": ctags, "speakers": nsp, "type": "stitched"}, evs))
    return out


def overlap(p: Promo, q: Promo) -> float:
    inter = 0.0
    for a in p.segments:
        for b in q.segments:
            if a.ep == b.ep:
                inter += max(0.0, min(a.end, b.end) - max(a.start, b.start))
    return inter / max(min(p.duration, q.duration), 1e-6)


def nms(cands: list[Promo], max_overlap=0.3, per_episode=3, limit=None):
    kept, per_ep = [], Counter()
    for c in sorted(cands, key=lambda p: -p.total):
        eps = {s.ep for s in c.segments}
        if any(per_ep[e] >= per_episode for e in eps):
            continue
        if any(overlap(c, k) > max_overlap for k in kept):
            continue
        kept.append(c)
        for e in eps:
            per_ep[e] += 1
        if limit and len(kept) >= limit:
            break
    return kept


def find_candidates(eps: list[Episode], use_markers=True, stitch=True, per_episode=3):
    spk = Counter(e.speaker for ep in eps for e in ep.events if e.kind == "dialogue")
    protagonist = spk.most_common(1)[0][0] if spk else ""
    idx = [EpisodeIndex(ep, protagonist, use_markers) for ep in eps]
    allc = []
    for i, ix in enumerate(idx):
        c = single_windows(ix)
        if stitch:
            nxt = idx[i + 1] if i + 1 < len(idx) and idx[i + 1].ep.ep == ix.ep.ep + 1 else None
            c += stitched_windows(ix, nxt)
        allc += nms(c, per_episode=per_episode)  # local NMS keeps memory small
    return nms(allc, per_episode=per_episode), idx, protagonist
