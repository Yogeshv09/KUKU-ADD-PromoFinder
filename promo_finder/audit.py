"""Data-quality audit of a parsed show. Everything here is deterministic code, no AI."""
from __future__ import annotations

from collections import Counter
from .parser import Episode, fmt


def audit_show(eps: list[Episode]) -> dict:
    issues = []
    kinds = Counter()
    speakers = Counter()
    total_dur = 0.0
    per_ep = []
    for ep in eps:
        total_dur += ep.duration
        dlg = [e for e in ep.events if e.kind == "dialogue"]
        for e in ep.events:
            kinds[e.kind] += 1
            if e.kind == "dialogue":
                speakers[e.speaker] += 1
            if e.end < e.start:
                issues.append(("negative_duration", ep.ep, e.uid, f"{fmt(e.start)}-{fmt(e.end)}"))
            if e.end - e.start > 15:
                issues.append(("very_long_event", ep.ep, e.uid, f"{e.end - e.start:.1f}s {e.kind}"))
            if not e.text:
                issues.append(("empty_text", ep.ep, e.uid, e.kind))
            sc = next((s for s in ep.scenes if s["scene"] == e.scene), None)
            if sc and sc["start"] is not None and sc["end"] is not None:
                if e.start < sc["start"] - 0.05 or e.end > sc["end"] + 0.5:
                    issues.append(("outside_scene_bounds", ep.ep, e.uid,
                                   f"event {fmt(e.start)}-{fmt(e.end)} scene {fmt(sc['start'])}-{fmt(sc['end'])}"))
        # overlapping dialogue from two different speakers (cutting there would clip someone)
        for a, b in zip(dlg, dlg[1:]):
            if b.start < a.end - 0.05 and a.speaker != b.speaker:
                issues.append(("dialogue_overlap", ep.ep, b.uid,
                               f"{a.speaker} ends {fmt(a.end)} > {b.speaker} starts {fmt(b.start)}"))
        # scene continuity
        for s1, s2 in zip(ep.scenes, ep.scenes[1:]):
            if s1["end"] is not None and s2["start"] is not None and abs(s2["start"] - s1["end"]) > 0.5:
                issues.append(("scene_gap", ep.ep, f"scene {s1['scene']}->{s2['scene']}",
                               f"{fmt(s1['end'])} -> {fmt(s2['start'])}"))
        # long silences (no dialogue) — fine visually but weak for promos
        gaps = [(a.end, b.start) for a, b in zip(dlg, dlg[1:]) if b.start - a.end > 8]
        for g in gaps:
            issues.append(("dialogue_silence_gt_8s", ep.ep, "", f"{fmt(g[0])} -> {fmt(g[1])}"))
        per_ep.append({"ep": ep.ep, "duration_s": round(ep.duration, 1), "scenes": len(ep.scenes),
                       "events": len(ep.events), "dialogue_lines": len(dlg),
                       "words_per_min": round(sum(len(e.text.split()) for e in dlg) / max(ep.duration / 60, 1e-6), 1)})
    ep_nums = [e.ep for e in eps]
    missing = sorted(set(range(1, max(ep_nums) + 1)) - set(ep_nums)) if ep_nums else []
    return {
        "episodes": len(eps), "missing_episode_numbers": missing,
        "total_runtime_min": round(total_dur / 60, 1),
        "episode_duration_s": {"min": min(p["duration_s"] for p in per_ep), "max": max(p["duration_s"] for p in per_ep),
                               "mean": round(sum(p["duration_s"] for p in per_ep) / len(per_ep), 1)},
        "event_counts": dict(kinds), "top_speakers": speakers.most_common(15),
        "issue_counts": dict(Counter(i[0] for i in issues)), "issues": issues, "per_episode": per_ep,
    }
