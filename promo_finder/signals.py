"""Per-event 'hook' and 'cliffhanger' signals.

Pure rules: lexicons + delivery tags + punctuation. Cheap, transparent and the same on every run,
so this layer can scan every second of every show. Lexicons are genre-level (microdrama), not
show-specific: nothing here names a character from the input pack.
"""
from __future__ import annotations

import re
from .parser import Event

# ---------- lexicons (genre-level) ----------
HOOK_LEX = {
    "violence": (3.0, r"\b(slap\w*|punch\w*|strik\w*|struck|hit|hits|kick\w*|chok\w*|strangl\w*|shov\w*|"
                      r"stab\w*|knife|dagger|blade|sword|gun|pistol|shot|shoots?|blood\w*|bleed\w*|wound\w*|"
                      r"collaps\w*|faint\w*|throttl\w*|drag\w*|seiz\w*|grab\w*|yank\w*|whip\w*|lash\w*|"
                      r"burn\w*|fire|flames?|crash\w*|shatter\w*|smash\w*|thorns?)\b"),
    "danger": (2.2, r"\b(poison\w*|arsenic|kill\w*|murder\w*|die|dies|dying|dead|death|corpse|hang\w*|"
                    r"execut\w*|prison|arrest\w*|chains?|handcuff\w*|guards?|scream\w*)\b"),
    "humiliation": (2.0, r"\b(kneel\w*|knees|beg\w*|humiliat\w*|disgrace\w*|shame\w*|worthless|plain|"
                         r"ugly|cripple\w*|beggar|filth\w*|trash|nothing|spit\w*|mock\w*|laugh\w* at|"
                         r"abandon\w*|jilt\w*|reject\w*|divorce\w*|annul\w*)\b"),
    "reveal": (2.4, r"\b(duke|duchess|heir|prince|princess|king|queen|billionaire|ceo|secret\w*|truth|"
                    r"lie|lied|lying|liar|betray\w*|pregnan\w*|baby|child|identity|real name|disguis\w*|"
                    r"who you really|who are you|it was you|you knew|engaged|marry\w*|married|wife|husband)\b"),
    "romance": (1.6, r"\b(kiss\w*|embrace\w*|lips|undress\w*|naked|desire|passion\w*)\b"),
    "confront": (1.4, r"\b(how dare|get out|never|you will pay|you'll pay|enough|liar|traitor|monster|"
                      r"witch|whore|harlot|thief)\b"),
}
CLIFF_LEX = {
    "threat": (2.6, r"\b(you will pay|you'll pay|or else|regret|destroy|ruin|kill|end you|make you|"
                    r"won't (?:live|survive)|last time|wait and see|soon|tonight|tomorrow|before dawn|"
                    r"if you|unless)\b"),
    "reveal": (2.4, r"\b(duke|heir|secret|truth|pregnan\w*|it was you|who are you|real name|"
                    r"you knew|i know (?:who|what)|the one who|is dead|alive|poison\w*|arsenic)\b"),
    "entrance": (2.2, r"\b(door (?:burst|bang|slam|swing|fl[iy]\w*)\w*|bursts? (?:in|open)|stands? in the doorway|"
                      r"appears?|steps? out of the shadows|a voice|someone|footsteps|arriv\w*|"
                      r"walks? in|witness\w*|watching|spying|overhear\w*|unaware)\b"),
    "danger": (1.8, r"\b(blade|knife|dagger|sword|gun|pistol|raises|lunges?|blood\w*|collaps\w*|"
                    r"faint\w*|chok\w*|scream\w*|grabs?|seiz\w*)\b"),
    "reaction": (2.0, r"\b(froz\w*|freez\w*|shock\w*|horrif\w*|terror|terrified|stunned|speechless|bewilder\w*|"
                      r"eyes (?:widen|wide|bulg)\w*|wide[- ]eyed|jaw (?:drops?|clench\w*)|realiz\w*|recogni\w*|"
                      r"drain\w* of (?:all )?colou?r|pale\w*|gasp\w*|stifl\w*|trembl\w*|stumbl\w*|disbelief|"
                      r"stares?|unblinking|knuckles|clench\w*|narrow\w*)\b"),
    "decision": (1.4, r"\b(marry me|will you|choose|decide|sign|confess|tell me|answer me|"
                      r"what will you do|what have you done)\b"),
}
# Explicit writer markers. Kept separate so evaluation can switch them off (they'd make the
# 'do we find the written episode-ending cliffhanger?' test circular).
MARKER_LEX = (3.0, r"\b(cliffhanger|cut to black|smash cut|freeze[- ]frame|ominous|sting|swells?|"
                   r"dramatic (?:musical )?chord|stunned silence|gasp\w*)\b")
CALM_LEX = (-1.6, r"\b(establishing|aerial|landscape|exterior of|wide shot of the (?:manor|estate|village|"
                  r"countryside|forest)|birds|sunrise|sunset|peaceful|quiet morning|serene|tranquil)\b")
RESOLVE_LEX = (-2.0, r"\b(thank you|thank god|goodnight|good night|safe now|it's over|relieved|relief|"
                     r"smiles? warmly|warm smile|peaceful\w*|content\w*|rest now|all is well|forgive you|"
                     r"gentle string music|tender\w*)\b")
BACKSTORY_LEX = r"\b(again|last night|yesterday|earlier|remember|as i said|as you said|after what happened|" \
                r"since that day|the other day|like before|once more|still)\b"
CONTEXT_OPENERS = re.compile(r"^(yes|no|because|but|and|so|then|fine|well|why\?|what\?|okay|very well)\b", re.I)

HIGH_AROUSAL = {
    "screaming", "shouting", "furious", "enraged", "hysterical", "outraged", "horrified", "terrified",
    "panicked", "frantic", "gasping", "sobbing", "weeping", "venomous", "menacing", "threatening",
    "sinister", "chilling", "cruel", "vicious", "deadly", "booming", "thunderous", "shocked", "stunned",
    "desperate", "piercing", "crying out", "spiteful", "vindictive", "malicious", "ruthless", "explosive",
    "raging", "seething", "accusing", "accusatory", "condemning", "betrayed", "shattered", "devastated",
}
MID_AROUSAL = {
    "cold", "mocking", "smug", "gloating", "taunting", "scornful", "contemptuous", "sneering", "derisive",
    "defiant", "fierce", "sharp", "harsh", "urgent", "demanding", "commanding", "trembling", "pleading",
    "heartbroken", "incredulous", "bitter", "dark", "ominous", "grim", "steely", "dismissive", "callous",
    "arrogant", "condescending", "breathless", "alarmed", "shaken", "tearful", "choked", "broken",
}

_compiled = {}


def _rx(p):
    if p not in _compiled:
        _compiled[p] = re.compile(p, re.I)
    return _compiled[p]


def _lex_hits(text: str, lex: dict) -> tuple[float, list[str]]:
    score, tags = 0.0, []
    for tag, (w, pat) in lex.items():
        n = len(_rx(pat).findall(text))
        if n:
            score += w * min(n, 2) ** 0.5
            tags.append(tag)
    return score, tags


def arousal(ev: Event) -> float:
    d = {x.lower() for x in ev.delivery}
    return 2.0 * len(d & HIGH_AROUSAL) ** 0.5 + 0.9 * len(d & MID_AROUSAL) ** 0.5


def hook_signal(ev: Event) -> tuple[float, list[str]]:
    """How much would this single event stop a scroll if it is on screen in the first 3s?"""
    s, tags = _lex_hits(ev.text, HOOK_LEX)
    if ev.kind == "dialogue":
        s += arousal(ev)
        if ev.text.endswith("!"):
            s += 0.8
        words = len(ev.text.split())
        if words <= 8 and s > 0:
            s += 0.6  # short, punchy line
        if CONTEXT_OPENERS.match(ev.text):
            s -= 1.5  # reply to something the viewer never saw
            tags.append("needs-context")
    elif ev.kind in ("action", "sfx"):
        s *= 1.15  # physical beats read instantly, even with sound off
    elif ev.kind == "camera":
        s *= 0.6   # camera notes describe framing more than story
    calm_w, calm_p = CALM_LEX
    if _rx(calm_p).search(ev.text):
        s += calm_w
        tags.append("calm")
    return s, tags


def cliff_signal(ev: Event, use_markers: bool = True) -> tuple[float, list[str]]:
    """How unresolved does the clip feel if it ends right after this event?"""
    s, tags = _lex_hits(ev.text, CLIFF_LEX)
    t = ev.text.strip()
    if ev.kind == "dialogue":
        s += 0.6 * arousal(ev)
        if "?" in t:
            s += 1.6
            tags.append("question")
        if t.endswith(("...", "…", "—", "-")):
            s += 1.4
            tags.append("interrupted")
    if use_markers:
        w, p = MARKER_LEX
        if _rx(p).search(t):
            s += w
            tags.append("marker")
    rw, rp = RESOLVE_LEX
    if _rx(rp).search(t):
        s += rw
        tags.append("resolves")
    return s, tags


_int_cache: dict[str, float] = {}


def intensity(ev: Event) -> float:
    key = f"{ev.ep}:{ev.uid}:{ev.start}"
    if key not in _int_cache:
        h, _ = hook_signal(ev)
        _int_cache[key] = max(h, 0.0) + (0.5 if ev.kind == "dialogue" else 0.0)
    return _int_cache[key]


def backstory_refs(text: str) -> int:
    return len(_rx(BACKSTORY_LEX).findall(text))
