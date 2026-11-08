"""Parse Kuku-style timed screenplays into a flat, typed event table.

Each episode file looks like:
    EPISODE NUMBER: Episode 1
    EPISODE LOGLINE: ...
    CONTINUITY NOTES: ...
    --- SCRIPT START ---
    SCENE 01
    Scene heading: INT. CATHEDRAL – DAY
    Scene start: 00:00.00
    Scene end: 02:18.00
    **CAMERA:** / **ACTION:** / **SOUND FX:** / **SPEAKER (Delivery, Tags):**
    Start: (00:00.00) | End: (00:04.80)
    <text>
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

TS_RE = re.compile(r"Start:\s*\((\d+):(\d+(?:\.\d+)?)\)\s*\|\s*End:\s*\((\d+):(\d+(?:\.\d+)?)\)")
HEADER_RE = re.compile(r"^\*\*(.+?):\*\*\s*$")
SCENE_TS_RE = re.compile(r"^Scene (start|end):\s*(\d+):(\d+(?:\.\d+)?)", re.I)
SCENE_NO_RE = re.compile(r"^SCENE\s+\d+\s*$", re.I)
EP_NUM_RE = re.compile(r"EPISODE NUMBER:\s*Episode\s*(\d+)", re.I)

NON_DIALOGUE = {"CAMERA": "camera", "ACTION": "action", "SOUND FX": "sfx", "SFX": "sfx", "SOUND": "sfx"}
VOICE_MARKERS = {"O.S.", "V.O.", "OFF-SCREEN", "CONT'D", "CONTINUING"}
HONORIFICS = ("LADY ", "LORD ", "SIR ", "THE ", "DOWAGER ")


def ts(m: str, s: str) -> float:
    return int(m) * 60 + float(s)


def fmt(t: float) -> str:
    m, s = divmod(max(t, 0.0), 60)
    return f"{int(m):02d}:{s:05.2f}"


@dataclass
class Event:
    uid: str            # e.g. "E07-012" -> episode 7, event 12 (stable ID the LLM refers to)
    ep: int
    scene: int
    idx: int
    kind: str           # camera | action | sfx | dialogue
    speaker: str        # canonical speaker ("" for non-dialogue)
    raw_speaker: str
    delivery: list[str]
    voice: str          # "", "O.S.", "V.O."
    text: str
    start: float
    end: float

    @property
    def dur(self) -> float:
        return self.end - self.start

    def to_dict(self):
        return asdict(self)


@dataclass
class Episode:
    ep: int
    path: str
    logline: str
    continuity: str
    scenes: list[dict] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)

    @property
    def duration(self) -> float:
        ends = [e.end for e in self.events] + [s["end"] for s in self.scenes if s["end"] is not None]
        return max(ends) if ends else 0.0


def canonical_speaker(raw: str) -> str:
    name = raw.upper().strip()
    for h in HONORIFICS:
        if name.startswith(h) and len(name) > len(h) + 2:
            name = name[len(h):]
    return name.strip()


def parse_header(h: str):
    """'LADY JULIANA (O.S.) (Cold, Commanding)' -> ('LADY JULIANA', ['Cold','Commanding'], 'O.S.')"""
    groups = re.findall(r"\(([^)]*)\)", h)
    name = re.sub(r"\([^)]*\)", "", h).strip()
    delivery, voice = [], ""
    for g in groups:
        g = g.strip()
        if g.upper() in VOICE_MARKERS:
            voice = g.upper()
            continue
        delivery += [x.strip() for x in g.split(",") if x.strip()]
    return name, delivery, voice


def parse_episode(path: str | Path) -> Episode:
    path = Path(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    ep_num, logline, cont = None, "", ""
    for ln in lines[:10]:
        if (m := EP_NUM_RE.search(ln)):
            ep_num = int(m.group(1))
        elif ln.startswith("EPISODE LOGLINE:"):
            logline = ln.split(":", 1)[1].strip()
        elif ln.startswith("CONTINUITY NOTES:"):
            cont = ln.split(":", 1)[1].strip()
    if ep_num is None:  # fall back to file name
        m = re.search(r"episode-(\d+)", path.name)
        ep_num = int(m.group(1)) if m else 0

    ep = Episode(ep=ep_num, path=str(path), logline=logline, continuity=cont)
    scene_no, cur, i = 0, None, 0
    while i < len(lines):
        ln = lines[i].strip()
        if SCENE_NO_RE.match(ln):
            scene_no += 1
            ep.scenes.append({"scene": scene_no, "heading": "", "start": None, "end": None})
        elif ln.lower().startswith("scene heading:") and ep.scenes:
            ep.scenes[-1]["heading"] = ln.split(":", 1)[1].strip()
        elif (m := SCENE_TS_RE.match(ln)) and ep.scenes:
            ep.scenes[-1][m.group(1).lower()] = ts(m.group(2), m.group(3))
        elif (m := HEADER_RE.match(ln)):
            header = m.group(1).strip()
            # timestamp is on the next non-empty line, text follows until blank line / next header
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            tm = TS_RE.search(lines[j]) if j < len(lines) else None
            if not tm:
                i += 1
                continue
            k = j + 1
            text_lines = []
            while k < len(lines) and lines[k].strip() and not HEADER_RE.match(lines[k].strip()) \
                    and not lines[k].startswith("---") and not SCENE_NO_RE.match(lines[k].strip()):
                text_lines.append(lines[k].strip())
                k += 1
            text = " ".join(text_lines).strip()
            name, delivery, voice = parse_header(header)
            kind = NON_DIALOGUE.get(name.upper(), "dialogue")
            if kind == "dialogue":
                text = text.strip().strip('"“”').strip()
            ev = Event(
                uid=f"E{ep_num:02d}-{len(ep.events):03d}", ep=ep_num, scene=max(scene_no, 1),
                idx=len(ep.events), kind=kind,
                speaker=canonical_speaker(name) if kind == "dialogue" else "",
                raw_speaker=name if kind == "dialogue" else "", delivery=delivery, voice=voice,
                text=text, start=ts(tm.group(1), tm.group(2)), end=ts(tm.group(3), tm.group(4)),
            )
            ep.events.append(ev)
            i = k
            continue
        i += 1
    ep.events.sort(key=lambda e: (e.start, e.end))
    for n, e in enumerate(ep.events):  # re-index after sorting so IDs are in time order
        e.idx, e.uid = n, f"E{ep_num:02d}-{n:03d}"
    return ep


def load_show(folder: str | Path) -> list[Episode]:
    files = sorted(Path(folder).rglob("*.txt"))
    eps = [parse_episode(f) for f in files]
    eps = [e for e in eps if e.events]
    eps.sort(key=lambda e: e.ep)
    return eps
