"""Promo Finder Studio — Streamlit UI for the promo_finder engine.

Run:  streamlit run app.py
Upload a .zip (or .txt files) of timed episode screenplays -> ranked 20-60 s promo clips.
No screenplay is stored: every run uses a temporary folder that is deleted afterwards.
"""
import html
import io
import os
import re
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from promo_finder.cli import run
from promo_finder.llm import PRESETS

st.set_page_config(page_title="Promo Finder Studio · Kuku", page_icon="🎬", layout="wide",
                   initial_sidebar_state="expanded")

ACCENT, GREEN = "#7c5cff", "#3ddc97"
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{--bg:#1d1e25;--panel:#272832;--panel2:#2e2f3a;--line:#363845;--ink:#ecedf3;--muted:#8b8d9e;
      --accent:#7c5cff;--accent2:#9b85ff;--green:#3ddc97;}
html,body,[class*="css"],.stApp{font-family:'Inter',sans-serif;}
.stApp{background:var(--bg);color:var(--ink);}
[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:1.4rem;max-width:1280px;}
#MainMenu,footer{visibility:hidden;}
h1,h2,h3{font-weight:800;letter-spacing:-.01em;color:#fff;}

/* ---- sidebar = purple icon rail + list panel ---- */
[data-testid="stSidebar"]{background:linear-gradient(90deg,var(--accent) 0 64px,#25262f 64px)!important;border-right:0;width:360px!important;min-width:360px!important;}
[data-testid="stSidebarUserContent"]{position:relative;padding-left:84px!important;padding-right:18px!important;}
.rail{position:fixed;left:0;top:64px;width:64px;display:flex;flex-direction:column;align-items:center;gap:28px;z-index:1000;}
[data-testid="stSidebar"][aria-expanded="false"] .rail{display:none;}
.rail span{color:rgba(255,255,255,.75);font-size:1.15rem;line-height:1;cursor:default;}
.rail span.on{color:#fff;}
.rail .badge{position:relative;}
.rail .badge:after{content:"";position:absolute;right:-6px;top:-4px;width:8px;height:8px;border-radius:50%;background:#ff6b6b;}
.rail .avatar{margin-top:30px;width:34px;height:34px;border-radius:50%;background:rgba(255,255,255,.18);
      display:flex;align-items:center;justify-content:center;font-size:.8rem;font-weight:800;color:#fff;}
.ptitle{font-size:1.05rem;font-weight:800;color:#fff;margin:2px 0 14px;}
.sec{font-size:.64rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:16px 0 8px;}
.task{background:var(--panel2);border-radius:12px;padding:12px 13px;margin-bottom:9px;}
.task.done{background:#20212a;}
.task .top{display:flex;justify-content:space-between;align-items:baseline;gap:8px;}
.task .t{font-size:.82rem;font-weight:800;color:#fff;}
.task .d{font-size:.66rem;color:var(--muted);white-space:nowrap;}
.task .x{font-size:.74rem;color:#a3a5b5;line-height:1.45;margin-top:6px;display:-webkit-box;-webkit-line-clamp:3;
      -webkit-box-orient:vertical;overflow:hidden;}
.task .v{font-size:.66rem;font-weight:800;margin-top:6px;}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] span{color:#d9dae4;}
[data-testid="stSidebar"] [data-testid="stExpander"] details{background:var(--panel2);border:0;border-radius:12px;}

/* ---- main cards ---- */
.lbl{font-size:.64rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:4px 0 10px;}
.box{background:var(--panel);border-radius:16px;padding:20px 22px;}
.ov{display:grid;grid-template-columns:1.3fr 2fr;gap:24px;align-items:end;}
.ov .k{font-size:.72rem;color:var(--muted);font-weight:600;}
.ov .big{font-size:2.2rem;font-weight:800;color:#fff;line-height:1.1;margin-top:2px;}
.ov .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;}
.ov .stats div{font-size:.7rem;color:var(--muted);font-weight:600;}
.ov .stats b{display:block;font-size:1.05rem;color:#fff;font-weight:800;margin-top:2px;}
.prog{display:flex;gap:10px;margin-top:18px;height:46px;}
.prog .fill{background:var(--accent);border-radius:10px;display:flex;align-items:center;padding:0 16px;font-weight:800;
      font-size:1.15rem;color:#fff;min-width:74px;white-space:nowrap;}
.prog .rest{flex:1;background:#353644;border-radius:10px;display:flex;align-items:center;padding:0 16px;font-size:.78rem;
      color:var(--muted);font-weight:600;}
table.pt{width:100%;border-collapse:collapse;border:none!important;}
table.pt tr,table.pt th,table.pt td{border:none!important;background:transparent!important;}
table.pt th{font-size:.66rem;color:var(--muted);font-weight:700;text-align:left;padding:0 6px 10px;}
table.pt td{font-size:.82rem;color:#fff;font-weight:700;padding:11px 6px;border-top:1px solid var(--line)!important;vertical-align:middle;}
table.pt td.m{color:#a3a5b5;font-weight:600;}
table.pt td.g{color:var(--green);font-weight:800;}
.mini{width:70px;height:6px;background:#3a3b49;border-radius:6px;overflow:hidden;}
.mini i{display:block;height:100%;background:var(--accent);border-radius:6px;}
.cal .head{display:flex;justify-content:space-between;align-items:center;font-size:.8rem;font-weight:800;color:#fff;margin-bottom:10px;}
.cal .head span{color:var(--muted);font-weight:600;}
.cal .grid{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;}
.cal .c{height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.72rem;font-weight:800;color:#fff;}
.cal .c.n{color:#5c5e6e;font-weight:600;}
.cal .c.s{background:var(--accent);}
.cal .leg{display:flex;gap:12px;margin-top:12px;font-size:.66rem;color:var(--muted);}
.cal .leg i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:middle;}

/* banner (keyed container) */
.st-key-banner{background:var(--accent);border-radius:16px;padding:22px 26px!important;position:relative;overflow:hidden;}
.st-key-banner:before{content:"";position:absolute;right:-90px;bottom:-140px;width:420px;height:300px;border-radius:50%;
      background:rgba(29,30,37,.35);}
.st-key-banner p{color:#fff!important;font-weight:800;font-size:1.02rem;line-height:1.45;margin:0;}
.st-key-banner .stButton>button:not([kind="primary"]),.st-key-banner .stDownloadButton>button:not([kind="primary"]){background:#a594ff!important;color:#fff!important;border:0!important;font-weight:800!important;
      border-radius:10px!important;}
[data-testid="stSidebar"] .stButton>button:not([kind="primary"]){border:1px solid #474959!important;}

/* promo cards */
.card{position:relative;background:var(--panel);border-radius:16px;padding:18px 20px 16px 84px;margin-bottom:10px;}
.rank{position:absolute;left:20px;top:18px;width:46px;height:46px;border-radius:12px;display:flex;align-items:center;
      justify-content:center;font-weight:800;font-size:1.2rem;color:#fff;background:var(--accent);}
.rank.dim{background:#3a3b49;}
.meta{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;}
.tag{font-size:.68rem;font-weight:700;border-radius:7px;padding:4px 8px;background:#33343f;color:#c9cad6;}
.tag.time{background:rgba(124,92,255,.16);color:#c3b7ff;}
.tag.score{background:rgba(61,220,151,.13);color:var(--green);}
.beat{display:grid;grid-template-columns:70px 1fr;gap:10px;align-items:start;margin:6px 0;}
.beat .lab{font-size:.6rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;padding:5px 0;border-radius:6px;text-align:center;}
.beat .lab.h{background:rgba(124,92,255,.18);color:#c3b7ff;}
.beat .lab.c{background:rgba(61,220,151,.13);color:var(--green);}
.beat .txt{color:#f2f3f8;font-size:.93rem;line-height:1.45;font-weight:600;}
.why{color:#a3a5b5;font-size:.82rem;margin-top:8px;line-height:1.5;}
.bars{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:12px;}
.bar .n{display:flex;justify-content:space-between;font-size:.66rem;color:var(--muted);font-weight:700;margin-bottom:4px;}
.bar .t{height:6px;border-radius:6px;background:#3a3b49;overflow:hidden;}
.bar .f{height:100%;border-radius:6px;background:var(--accent);}
.script{background:#202129;border-radius:12px;padding:8px 14px;}
.line{display:grid;grid-template-columns:104px 1fr;gap:10px;padding:5px 0;border-bottom:1px solid #2c2d38;font-size:.85rem;}
.line:last-child{border-bottom:0;}
.line .ts{color:#b3a6ff;font-size:.74rem;font-weight:700;padding-top:2px;}
.line .sp{color:#fff;font-weight:800;}
.line .act{color:var(--muted);font-style:italic;}
.ok{color:var(--green);font-weight:800;} .bad{color:#ff6b8a;font-weight:800;}
.foot{text-align:center;color:#5c5e6e;font-size:.74rem;margin-top:34px;}

/* widgets */
[data-testid="stTabs"] button p{font-weight:700;font-size:.9rem;}
.stButton>button,.stDownloadButton>button{border-radius:10px!important;font-weight:700!important;}
.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"]{background:var(--accent)!important;color:#fff!important;border:0!important;}
.stButton>button:not([kind="primary"]),.stDownloadButton>button:not([kind="primary"]){background:var(--panel2)!important;
      color:#e9e9f2!important;border:0!important;}
[data-testid="stFileUploaderDropzone"]{background:var(--panel2)!important;border:1px dashed #4a4c5c!important;border-radius:12px!important;}
[data-testid="stExpander"] details{background:var(--panel);border:0;border-radius:14px;}
[data-testid="stCaptionContainer"]{color:var(--muted)!important;}
</style>
""", unsafe_allow_html=True)

E = lambda x: html.escape(str(x), quote=True)

# --------------------------------------------------------------------------- demo show (fictional, safe to share)
def _ts(t):
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


DEMO_EPISODES = [
    ("The fisherman's daughter is publicly accused of theft — until a stranger steps off a ship.", "EXT. HARBOUR MARKET – DUSK", [
        ("Wide shot of a storm-lashed harbour market at dusk.", [("SOUND FX", "Thunder rolls across the water.", 2.5),
                                                                ("MARA (Cheerful)", "Fresh catch! Two coins a basket!", 2.5)]),
        ("Medium shot: Lady Vane pushes through the crowd, flanked by guards.", [
            ("LADY VANE (Cold, Commanding)", "That's her. The fisherman's girl.", 3.0),
            ("MARA (Confused)", "My lady? Is something wrong?", 2.5)]),
        ("Close-up on Lady Vane's raised hand.", [("ACTION", "Lady Vane slaps Mara across the face. The crowd gasps.", 2.5),
                                                 ("LADY VANE (Furious, Shouting)", "You stole my mother's sapphire, you filthy thief!", 3.5)]),
        ("Close-up on Mara, cheek burning, eyes wide with shock.", [
            ("MARA (Trembling, Shocked)", "I have never set foot in your house!", 3.0),
            ("LADY VANE (Venomous)", "Then explain why my maid saw you at the gate.", 3.5)]),
        ("Two-shot as a guard grabs Mara's arm.", [("ACTION", "A guard seizes Mara and drags her toward the cart.", 3.0),
                                                   ("MARA (Desperate, Screaming)", "Let me go! Father! Somebody help me!", 3.0)]),
        ("Wide shot of the silent crowd turning away.", [
            ("FISHERMAN (Pleading)", "Please, my lady, she is only a child of the sea.", 3.5),
            ("LADY VANE (Mocking)", "Then let the sea pay her bail.", 2.5)]),
        ("Medium shot: a cloaked stranger steps off a ship onto the dock.", [
            ("ACTION", "A tall stranger in a dark cloak steps between Mara and the guards.", 3.0),
            ("STRANGER (Cold, Menacing)", "Take your hands off her.", 2.5)]),
        ("Close-up on Lady Vane, sneering.", [("LADY VANE (Arrogant)", "And who are you to give orders in my harbour?", 3.0),
                                              ("STRANGER (Calm)", "Someone who knows where your sapphire really is.", 3.0)]),
        ("Extreme close-up on Lady Vane's face draining of colour.", [("SOUND FX", "A sharp, ominous sting.", 1.5),
                                                                       ("LADY VANE (Stunned)", "What did you say?", 2.0)]),
        ("Two-shot: the stranger leans close to Mara.", [
            ("STRANGER (Whispering)", "Your mother didn't drown, Mara. She was the Duchess of Greywater.", 4.5),
            ("MARA (Shocked, Breathless)", "What? Who are you?", 2.5)]),
        ("Cut to black.", []),
    ]),
    ("Aboard the stranger's ship, Mara learns the truth — and Lady Vane comes to finish the job.", "INT. SHIP'S CABIN – NIGHT", [
        ("Interior of a candle-lit cabin aboard the stranger's ship.", [
            ("MARA (Defiant)", "Tell me the truth. Who was my mother?", 3.0),
            ("STRANGER (Grave)", "The rightful heir to Greywater. And so are you.", 3.5)]),
        ("Close-up on an old locket in the stranger's palm.", [
            ("ACTION", "He opens the locket: a portrait of a woman with Mara's eyes.", 3.0),
            ("MARA (Trembling)", "That's her... that's my mother.", 2.5)]),
        ("Medium shot: the cabin door bursts open.", [("SOUND FX", "The door slams against the wall.", 1.0),
                                                      ("ACTION", "Lady Vane bursts in with two guards, a dagger in her hand.", 3.0),
                                                      ("LADY VANE (Menacing)", "Kill them both. No heir leaves this ship alive.", 3.5)]),
        ("Wide shot as the guards lunge forward.", [("ACTION", "The stranger draws his sword and blocks the first blade.", 3.0),
                                                    ("STRANGER (Shouting)", "Mara, get behind me!", 2.0)]),
        ("Close-up on Mara grabbing a lantern.", [("ACTION", "Mara hurls the lantern; fire spreads across the deck.", 3.0),
                                                  ("MARA (Furious)", "You burned my father's boat. Now feel the fire!", 3.5)]),
        ("Medium shot: Lady Vane cornered by flames.", [
            ("LADY VANE (Desperate)", "You think a fisherman's girl can take my title?", 3.5),
            ("MARA (Cold)", "It was never your title.", 2.5)]),
        ("Two-shot: the stranger lowers his sword, breathing hard.", [
            ("STRANGER (Quiet)", "She knew who you were from the start.", 3.0),
            ("MARA (Shocked)", "She knew? Then who sent her to find me?", 3.5)]),
        ("Extreme close-up on Lady Vane smiling through the smoke.", [
            ("LADY VANE (Sinister, Whispering)", "Ask your father.", 2.5), ("SOUND FX", "A dramatic chord swells.", 1.5)]),
        ("Cut to black.", []),
    ]),
]


def demo_files() -> dict:
    """Fictional 2-episode show in the same timed-screenplay format as the real input pack."""
    out = {}
    for n, (logline, heading, shots) in enumerate(DEMO_EPISODES, 1):
        t, blocks = 0.0, []
        for cam, beats in shots:
            s0 = t
            body = []
            for head, text, d in beats:
                body.append(f"**{head}:**\nStart: ({_ts(t)}) | End: ({_ts(t + d)})\n{text}\n")
                t += d
            if not beats:
                t += 1.0
            blocks.append(f"**CAMERA:**\nStart: ({_ts(s0)}) | End: ({_ts(t)})\n{cam}\n")
            blocks += body
        txt = (f"EPISODE NUMBER: Episode {n}\nEPISODE LOGLINE: {logline}\nCONTINUITY NOTES: Fictional demo.\n\n"
               f"--- SCRIPT START ---\n\nSCENE 01\nScene heading: {heading}\nScene start: 00:00.00\nScene end: {_ts(t)}\n\n"
               + "\n".join(blocks) + "\n--- SCRIPT END ---\n")
        out[f"The Lighthouse Heir (demo)/episode-{n:03d}.txt"] = txt
    return out


def demo_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, txt in demo_files().items():
            z.writestr(name, txt)
    return buf.getvalue()

# --------------------------------------------------------------------------- helpers
def seg_label(r, sep=" · "):
    return " + ".join(f"E{s['episode']}{sep}{s['start']}–{s['end']}" for s in r["segments"])


def short_seg(r):
    s0 = r["segments"][0]
    extra = f" +{len(r['segments']) - 1}" if len(r["segments"]) > 1 else ""
    return f"E{s0['episode']} · {s0['start'][:5]}–{s0['end'][:5]}{extra}"


def score(r, k):
    s = r["scores"]
    return float(s.get(f"llm_{k}", s.get(k, 0.0)))


def bars(r):
    items = [("Hook", score(r, "hook")), ("Cliffhanger", score(r, "cliff")),
             ("Standalone", score(r, "standalone")), ("Intensity", float(r["scores"].get("body", 0)))]
    return '<div class="bars">' + "".join(
        f'<div class="bar"><div class="n"><span>{k}</span><span>{v:.1f}</span></div>'
        f'<div class="t"><div class="f" style="width:{max(3, min(100, v * 10)):.0f}%"></div></div></div>'
        for k, v in items) + "</div>"


def card(r, slot=None):
    num = slot if slot else r["rank"]
    top = slot is not None or r["rank"] <= 3
    tags = [f'<span class="tag time">◷ {E(seg_label(r))}</span>', f'<span class="tag">{r["duration_s"]:.0f}s</span>',
            f'<span class="tag">{E(r["category"])}</span>', f'<span class="tag">{E(r["type"])}</span>',
            f'<span class="tag score">★ {r["scores"]["total"]:.2f}</span>']
    if r.get("described_by") and r["described_by"] != "rules":
        tags.append(f'<span class="tag">AI: {E(r["described_by"])}</span>')
    return (f'<div class="card"><div class="rank {"" if top else "dim"}">{num}</div>'
            f'<div class="meta">{"".join(tags)}</div>'
            f'<div class="beat"><div class="lab h">Hook</div><div class="txt">{E(r["hook"])}</div></div>'
            f'<div class="beat"><div class="lab c">Cliff</div><div class="txt">{E(r["cliffhanger"])}</div></div>'
            f'<div class="why">{E(r["why"])}</div>{bars(r)}</div>')


LINE_RE = re.compile(r"^(E\d+) (\d\d:\d\d\.\d\d) (.*)$")


def script_html(lines):
    rows = []
    for ln in lines:
        m = LINE_RE.match(ln)
        if not m:
            rows.append(f'<div class="line"><span></span><span>{E(ln)}</span></div>')
            continue
        ep, t, rest = m.groups()
        if rest.startswith("["):
            kind, _, txt = rest[1:].partition("] ")
            body = f'<span class="act">{E(kind.upper())} · {E(txt)}</span>'
        else:
            who, _, txt = rest.partition(": ")
            body = f'<span class="sp">{E(who)}</span> {E(txt)}'
        rows.append(f'<div class="line"><span class="ts">{E(ep)} · {E(t)}</span><span>{body}</span></div>')
    return '<div class="script">' + "".join(rows) + "</div>"


def verdict(rank):
    return st.session_state.get(f"v_{rank}", "Not reviewed")


def write_inputs(uploads, folder: Path):
    """Uploaded .zip / .txt files -> a temp folder the engine can read."""
    n = 0
    for name, data in uploads:
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for item in z.infolist():
                    if item.is_dir() or not item.filename.lower().endswith(".txt") or "__MACOSX" in item.filename:
                        continue
                    if item.file_size > 5 * 1024 * 1024:
                        raise ValueError(f"{item.filename} is larger than 5 MB")
                    target = folder / Path(item.filename).name
                    target.write_bytes(z.read(item))
                    n += 1
        elif name.lower().endswith(".txt"):
            (folder / Path(name).name).write_bytes(data)
            n += 1
    if n == 0:
        raise ValueError("No .txt screenplays found in the upload.")
    return n


def analyse(uploads, label, provider, model, key, judge_top, stitch, full_eval):
    key_env = "LLM_API_KEY"
    if provider and key:
        os.environ[key_env] = key            # removed again in `finally` so it never leaks to other visitors
    if provider in ("gemini", "groq", "openrouter"):
        os.environ.setdefault("LLM_MIN_INTERVAL", "6")   # free tiers: a few requests per minute
    try:
        with tempfile.TemporaryDirectory(prefix="promo_") as tmp:
            src = Path(tmp) / "show"
            src.mkdir()
            n_files = write_inputs(uploads, src)
            out = Path(tmp) / "out"
            box = st.status(f"Reading {n_files} screenplay files…", expanded=True)
            log_area = box.empty()
            lines = []

            def log(msg):
                lines.append(str(msg)[:220])
                log_area.code("\n".join(lines[-10:]), language=None)

            recs, ev, audit, meta = run(str(src), str(out), provider=provider, model=model or None,
                                        judge_top=judge_top, stitch=stitch, eval_extra=full_eval, log=log)
            box.update(label=f"Done — {len(recs)} promos from {meta['episodes']} episodes in {meta['runtime_s']} s",
                       state="complete", expanded=False)
            files = {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}
    finally:
        if provider and key:
            os.environ.pop(key_env, None)
    meta["source"] = label
    return {"recs": recs, "ev": ev, "audit": audit, "meta": meta, "files": files}

# --------------------------------------------------------------------------- run triggers (callbacks run before the rerun)
def _want_demo():
    st.session_state["_action"] = "demo"


def _want_run():
    st.session_state["_action"] = "run"


res = st.session_state.get("res")

# --------------------------------------------------------------------------- sidebar: rail + panel
with st.sidebar:
    st.markdown('<div class="rail"><span class="on" title="Menu">☰</span><span title="Home">⌂</span>'
                '<span class="badge" title="Queue">✉</span><span title="Top promos">★</span><span title="Promo map">▦</span>'
                '<span title="Quality">▮▮</span><span title="Settings">⚙</span><div class="avatar">PF</div></div>',
                unsafe_allow_html=True)
    st.markdown('<div class="ptitle">Promo Finder</div>', unsafe_allow_html=True)

    with st.expander("New run" if res else "Start a run", expanded=not res):
        uploads = st.file_uploader("Screenplays (.zip or .txt)", type=["zip", "txt"], accept_multiple_files=True)
        st.button("Find promos", type="primary", disabled=not uploads, width="stretch", on_click=_want_run)
        st.button("Try the demo show", width="stretch", on_click=_want_demo, key="demo_side")
        choice = st.selectbox("AI judge", ["Rules only (free, no key)", "gemini", "groq", "openrouter", "openai", "anthropic"])
        provider = None if choice.startswith("Rules") else choice
        model = key = ""
        judge_top = 20
        if provider:
            model = st.text_input("Model", value="gemini-flash-latest" if provider == "gemini" else PRESETS[provider][2])
            env_name = PRESETS[provider][3]
            has_secret = bool(env_name and os.getenv(env_name))
            key = st.text_input("API key", type="password",
                                placeholder="saved in app secrets" if has_secret else "paste key, then press Enter")
            judge_top = st.slider("Promos the AI re-scores", 5, 60, 15, step=5)
        stitch = st.toggle("Allow stitched promos", value=True)
        full_eval = st.toggle("Stability test (+~60 s)", value=False)

    if res:
        recs_ = res["recs"]
        slate_ = sorted([r for r in recs_ if r.get("post_first_slot")], key=lambda r: r["post_first_slot"])
        active = [r for r in slate_ if verdict(r["rank"]) == "Not reviewed"]
        done = [r for r in recs_ if verdict(r["rank"]) != "Not reviewed"]
        st.markdown('<div class="sec">Active · post first</div>', unsafe_allow_html=True)
        if not active:
            st.caption("All slate promos reviewed 🎉")
        st.markdown("".join(
            f'<div class="task"><div class="top"><span class="t">#{r["post_first_slot"]} · {E(short_seg(r))}</span>'
            f'<span class="d">{r["duration_s"]:.0f}s</span></div><div class="x">{E(r["hook"])}</div></div>'
            for r in active), unsafe_allow_html=True)
        st.markdown('<div class="sec">Resolved</div>', unsafe_allow_html=True)
        if not done:
            st.caption("Review clips in the Promos tab: they move here.")
        colour = {"✅": GREEN, "✂": "#ffc75f", "❌": "#ff6b8a"}
        st.markdown("".join(
            f'<div class="task done"><div class="top"><span class="t">#{r["rank"]} · {E(short_seg(r))}</span>'
            f'<span class="d">{r["duration_s"]:.0f}s</span></div><div class="x">{E(r["hook"])}</div>'
            f'<div class="v" style="color:{colour.get(verdict(r["rank"])[:1], "#fff")}">{E(verdict(r["rank"]))}</div></div>'
            for r in done), unsafe_allow_html=True)
        if st.button("Clear results", width="stretch"):
            for k in list(st.session_state):
                del st.session_state[k]
            st.rerun()
    st.caption("🔒 Files are processed in a temporary folder and deleted after each run.")


def need_key():
    if not provider or key:
        return False
    env_name = PRESETS[provider][3]
    return not (env_name and os.getenv(env_name)) and not os.getenv("LLM_API_KEY")


# --------------------------------------------------------------------------- header
st.markdown('<div class="lbl">Kuku · AI Generalist · Problem 1</div>', unsafe_allow_html=True)
st.markdown("## Find the moment. Make them watch.")
st.caption("Timed microdrama screenplays in → ranked 20–60 s promo clips out: timestamps, the hook, the cliffhanger "
           "and why each one works.")

action = st.session_state.pop("_action", None)
if action:
    if need_key():
        st.error("Paste an API key in the sidebar (and press Enter), or choose **Rules only**.")
    else:
        try:
            if action == "demo":
                new = analyse([("demo.zip", demo_zip_bytes())], "The Lighthouse Heir (fictional demo)",
                              provider, model, key, judge_top, stitch, full_eval)
            else:
                new = analyse([(f.name, f.getvalue()) for f in uploads], ", ".join(f.name for f in uploads[:2]),
                              provider, model, key, judge_top, stitch, full_eval)
            for k in [k for k in st.session_state if k.startswith(("v_", "n_"))]:
                del st.session_state[k]
            st.session_state["res"] = new
            st.rerun()
        except (ValueError, zipfile.BadZipFile, SystemExit) as ex:
            st.error(f"Could not read the screenplays: {ex}")
        except Exception as ex:  # keep the UI alive and show what went wrong
            st.error(f"Analysis failed: {type(ex).__name__}: {ex}")

# --------------------------------------------------------------------------- empty state
if not res:
    st.markdown('<div class="lbl">Overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="box ov"><div><div class="k">Promos found</div><div class="big">—</div></div>'
                '<div class="stats"><div>Input<b>.zip / .txt</b></div><div>Clip length<b>20–60 s</b></div>'
                '<div>Cuts<b>shot edges</b></div><div>AI judge<b>optional</b></div></div>'
                '<div class="prog" style="grid-column:1/-1"><div class="fill">0%</div><div class="rest">Upload a show in the sidebar, '
                'or try the demo</div></div></div>',
                unsafe_allow_html=True)
    st.write("")
    a, b = st.columns([2, 1])
    with a:
        st.markdown('<div class="lbl">How it works</div>', unsafe_allow_html=True)
        st.markdown('<div class="box"><table class="pt"><tr><th>Step</th><th>What happens</th><th>Owner</th></tr>'
                    '<tr><td>Parse</td><td class="m">Screenplay → timed shots, actions, sound, dialogue</td><td class="g">code</td></tr>'
                    '<tr><td>Legal cuts</td><td class="m">Shot boundaries that never split a spoken line</td><td class="g">code</td></tr>'
                    '<tr><td>Score</td><td class="m">Hook (first 3 s) · cliffhanger · standalone · intensity</td><td class="g">rules</td></tr>'
                    '<tr><td>Judge</td><td class="m">Optional AI re-scores the shortlist by line ID</td><td class="g">AI</td></tr>'
                    '<tr><td>Review</td><td class="m">Editor marks Post / Trim / Reject → review sheet</td><td class="g">human</td></tr>'
                    '</table></div>', unsafe_allow_html=True)
    with b:
        st.markdown('<div class="lbl">Expected format</div>', unsafe_allow_html=True)
        st.markdown('<div class="box" style="font-size:.8rem;color:#a3a5b5;line-height:1.6">One <code>.txt</code> per episode:'
                    '<br><code>**NAME (Delivery):**</code><br><code>Start: (00:04.80) | End: (00:07.10)</code><br>'
                    '<code>line of dialogue</code></div>', unsafe_allow_html=True)
        st.write("")
        st.download_button("Download demo screenplays", demo_zip_bytes(), "lighthouse_heir_demo.zip", "application/zip",
                           width="stretch")
    st.write("")
    with st.container(key="banner"):
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.markdown("Try it on a short fictional drama — no confidential scripts needed.")
        c2.button("Run the demo", on_click=_want_demo, width="stretch", key="demo_banner")
    st.markdown('<div class="foot">PROMO FINDER STUDIO · transparent, reproducible ranking</div>', unsafe_allow_html=True)
    st.stop()

# --------------------------------------------------------------------------- dashboard
recs, ev, audit, meta, files = res["recs"], res["ev"], res["audit"], res["meta"], res["files"]
s = ev["structural"]
slate = sorted([r for r in recs if r.get("post_first_slot")], key=lambda r: r["post_first_slot"])
n_rev = sum(verdict(r["rank"]) != "Not reviewed" for r in slate)
pct = round(100 * n_rev / len(slate)) if slate else 0

st.markdown(f'<div class="lbl">Overview · {E(meta.get("source", meta["show"]))}</div>', unsafe_allow_html=True)
st.markdown(f'<div class="box"><div class="ov"><div><div class="k">Promos found</div><div class="big">{len(recs)}</div></div>'
            f'<div class="stats"><div>Episodes<b>{meta["episodes"]}</b></div><div>Covered<b>{s["episodes_covered"]}/{meta["episodes"]}</b></div>'
            f'<div>Avg length<b>{s["mean_duration_s"]} s</b></div>'
            f'<div>Clean cuts<b>{"100%" if not s["mid_line_cuts"] else len(s["mid_line_cuts"])}</b></div></div></div>'
            f'<div class="prog"><div class="fill" style="width:{max(pct, 8)}%">{pct}%</div>'
            f'<div class="rest">of the posting slate reviewed · {n_rev}/{len(slate)} · model: {E(meta["model"])}</div></div></div>',
            unsafe_allow_html=True)
st.write("")

left, right = st.columns([2, 1])
with left:
    st.markdown('<div class="lbl">Top promos</div>', unsafe_allow_html=True)
    rows = "".join(
        f'<tr><td>#{r["rank"]}</td><td>{E(short_seg(r))}</td><td class="m">{r["duration_s"]:.0f}s</td>'
        f'<td><div class="mini"><i style="width:{min(100, score(r, "hook") * 10):.0f}%"></i></div></td>'
        f'<td class="g">{score(r, "cliff") * 10:.0f}%</td></tr>' for r in recs[:6])
    st.markdown(f'<div class="box"><table class="pt"><tr><th>Rank</th><th>Clip</th><th>Length</th><th>Hook</th>'
                f'<th>Cliffhanger</th></tr>{rows}</table></div>', unsafe_allow_html=True)
with right:
    st.markdown('<div class="lbl">Episodes</div>', unsafe_allow_html=True)
    with_promo = {e for r in recs for e in r["episodes"]}
    slate_eps = {r["first_ep"] if "first_ep" in r else r["episodes"][0] for r in slate}
    cells = "".join(
        f'<div class="c {"s" if p["ep"] in slate_eps else ("" if p["ep"] in with_promo else "n")}" '
        f'title="Episode {p["ep"]}">{p["ep"]}</div>' for p in audit["per_episode"])
    st.markdown(f'<div class="box cal"><div class="head"><span>‹</span>Season · {meta["episodes"]} episodes<span>›</span></div>'
                f'<div class="grid">{cells}</div><div class="leg"><span><i style="background:{ACCENT}"></i>post first</span>'
                f'<span><i style="background:#fff"></i>has promos</span><span><i style="background:#5c5e6e"></i>none</span></div></div>',
                unsafe_allow_html=True)
st.write("")

review = pd.DataFrame([{"rank": r["rank"], "post_first_slot": r.get("post_first_slot") or "", "clip": seg_label(r, " "),
                        "duration_s": r["duration_s"], "hook": r["hook"], "cliffhanger": r["cliffhanger"],
                        "score": r["scores"]["total"], "editor_verdict": verdict(r["rank"]),
                        "editor_notes": st.session_state.get(f"n_{r['rank']}", "")} for r in recs])
with st.container(key="banner"):
    c1, c2 = st.columns([3, 1], vertical_alignment="center")
    c1.markdown("Review the slate in the Promos tab, then hand your editor the sheet with every verdict.")
    c2.download_button("Download review sheet", review.to_csv(index=False).encode("utf-8-sig"), "editor_review.csv",
                       "text/csv", width="stretch")
st.write("")

t1, t2, t3, t4, t5 = st.tabs(["Post first", "Promos & review", "Promo map", "Quality", "Exports"])

with t1:
    st.caption("Best quality × earliest in the funnel; max one per episode and three per hook type.")
    for r in slate:
        st.markdown(card(r, slot=r["post_first_slot"]), unsafe_allow_html=True)
        with st.expander(f"Script · slot #{r['post_first_slot']} · {seg_label(r)}"):
            st.markdown(script_html(r["transcript"]), unsafe_allow_html=True)

with t2:
    f1, f2, f3, f4 = st.columns([1.4, 1, 1, 1])
    q = f1.text_input("Search", placeholder="e.g. poison, duke, slap")
    ep_sel = f2.multiselect("Episodes", sorted(with_promo))
    cat_sel = f3.multiselect("Hook type", sorted({r["category"] for r in recs}))
    sort = f4.selectbox("Sort by", ["Quality rank", "Episode order", "Hook score", "Cliffhanger score", "Shortest first"])
    view = [r for r in recs
            if (not q or q.lower() in f"{r['hook']} {r['cliffhanger']} {r['why']}".lower())
            and (not ep_sel or set(ep_sel) & set(r["episodes"])) and (not cat_sel or r["category"] in cat_sel)]
    view.sort(key={"Quality rank": lambda r: r["rank"],
                   "Episode order": lambda r: (r["episodes"][0], r["segments"][0]["start_s"]),
                   "Hook score": lambda r: -score(r, "hook"), "Cliffhanger score": lambda r: -score(r, "cliff"),
                   "Shortest first": lambda r: r["duration_s"]}[sort])
    n_view = len(view)
    opts = sorted({o for o in (10, 20, 50) if o < n_view} | {n_view}) if n_view else [0]
    show_n = st.select_slider("Show", options=opts, value=min(20, n_view) if n_view else 0,
                              format_func=lambda v: f"all {v}" if v == n_view else str(v)) if len(opts) > 1 else n_view
    st.caption(f"Showing {min(show_n, n_view)} of {n_view} matching promos ({len(recs)} total)")
    if not view:
        st.info("No promos match these filters.")
    for r in view[:show_n]:
        st.markdown(card(r), unsafe_allow_html=True)
        with st.expander(f"Script & review · #{r['rank']}  —  {verdict(r['rank'])}"):
            st.markdown(script_html(r["transcript"]), unsafe_allow_html=True)
            c1, c2 = st.columns([1, 2])
            c1.selectbox("Editor verdict", ["Not reviewed", "✅ Post it", "✂ Needs a trim", "❌ Reject"], key=f"v_{r['rank']}")
            c2.text_input("Notes (better start/end, issues…)", key=f"n_{r['rank']}")
            if r.get("llm_issues"):
                st.warning("AI flagged: " + ", ".join(map(str, r["llm_issues"])))

with t3:
    st.caption("Each row is an episode; bars are promo windows (brighter = higher score). Hover for the hook.")
    rows = [{"Episode": f"E{g['episode']:02d}", "start": g["start_s"], "end": g["end_s"], "Score": r["scores"]["total"],
             "Rank": r["rank"], "Hook": r["hook"][:90], "Clip": seg_label(r)} for r in recs for g in r["segments"]]
    dur = pd.DataFrame([{"Episode": f"E{p['ep']:02d}", "start": 0.0, "end": p["duration_s"]} for p in audit["per_episode"]])
    try:
        import altair as alt
        base = alt.Chart(dur).mark_bar(color="#30313d", cornerRadius=4).encode(
            y=alt.Y("Episode:N", sort=None, title=None), x=alt.X("start:Q", title="seconds into episode"), x2="end:Q")
        fg = alt.Chart(pd.DataFrame(rows)).mark_bar(cornerRadius=4).encode(
            y=alt.Y("Episode:N", sort=None), x="start:Q", x2="end:Q",
            color=alt.Color("Score:Q", scale=alt.Scale(range=["#4a3a99", ACCENT, GREEN]), legend=None),
            tooltip=["Rank", "Clip", "Score", "Hook"])
        st.altair_chart((base + fg).properties(height=max(160, 16 * len(dur)), background="transparent")
                        .configure_view(strokeWidth=0).configure_axis(labelColor="#8b8d9e", titleColor="#8b8d9e",
                                                                      gridColor="#2c2d38", domainColor="#363845"),
                        width="stretch")
    except Exception:
        st.bar_chart(pd.DataFrame(rows).groupby("Episode").size())
    a, b = st.columns(2)
    a.markdown("**Promos by hook type**")
    a.bar_chart(pd.Series([r["category"] for r in recs]).value_counts(), color=ACCENT)
    b.markdown("**Promo length (seconds)**")
    b.bar_chart(pd.cut(pd.Series([r["duration_s"] for r in recs]), [20, 25, 30, 35, 40, 45, 50, 55, 60],
                       include_lowest=True).value_counts().sort_index().rename(index=str), color=GREEN)

with t4:
    checks = [("Every promo is 20–60 s", not s["duration_violations"]),
              ("No cut inside a spoken line", not s["mid_line_cuts"]),
              ("Every episode has at least one promo", not s["episodes_without_promo"]),
              ("Hook, cliffhanger and why filled for every promo", all(r["hook"] and r["cliffhanger"] and r["why"] for r in recs)),
              ("No missing episode numbers", not audit["missing_episode_numbers"])]
    st.markdown('<div class="box">' + "".join(
        f'<div style="margin:5px 0">{"<span class=ok>PASS</span>" if ok else "<span class=bad>FAIL</span>"}&nbsp;&nbsp;{E(l)}</div>'
        for l, ok in checks) + "</div>", unsafe_allow_html=True)
    st.write("")
    sil = ev.get("silver_cliffhanger_test")
    if sil:
        st.markdown("**Silver cliffhanger test**: is each episode's written ending in the top 20 % of possible end points? "
                    "(random = 20 %; held-out = odd episodes not used for tuning)")
        st.dataframe(pd.DataFrame([{"Episodes": sp, "Writer cue words": "off" if mk == "markers_off" else "on",
                                    "In top 20 %": f"{v['share_in_top_20pct']:.0%}", "Median percentile": v["median_percentile"]}
                                   for sp, d in sil.items() for mk, v in d.items()]), hide_index=True, width="stretch")
    stab = ev.get("weight_stability")
    if stab:
        st.markdown(f"**Weight stability** (±30 % weights, {stab['trials']} trials): top-10 overlap "
                    f"**{stab['top10_exact_jaccard_mean']:.2f}** exact · **{stab['top10_episode_jaccard_mean']:.2f}** same episodes")
    if not sil and not stab:
        st.caption("Turn on **Stability test** in the sidebar for the silver cliffhanger and stability checks.")
    names = {"dialogue_silence_gt_8s": "Dialogue-free stretches > 8 s", "dialogue_overlap": "Overlapping lines (two speakers)",
             "very_long_event": "Very long single block (> 15 s)", "scene_gap": "Gaps between scenes",
             "outside_scene_bounds": "Events outside their scene", "negative_duration": "Negative durations",
             "empty_text": "Empty blocks"}
    ic = audit.get("issue_counts", {})
    st.markdown("**Data-quality audit**")
    if ic:
        st.dataframe(pd.DataFrame([{"Check": names.get(k, k), "Count": v} for k, v in ic.items()]), hide_index=True, width="stretch")
    else:
        st.success("No data-quality issues found.")
    with st.expander("Per-episode stats"):
        st.dataframe(pd.DataFrame(audit["per_episode"]), hide_index=True, width="stretch")

with t5:
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
        z.writestr("editor_review.csv", review.to_csv(index=False))
    c1, c2 = st.columns(2)
    c1.download_button("Everything (zip)", zbuf.getvalue(), "promo_finder_outputs.zip", "application/zip",
                       type="primary", width="stretch")
    c2.download_button("Editor review sheet", review.to_csv(index=False).encode("utf-8-sig"), "editor_review.csv",
                       "text/csv", width="stretch", key="rev2")
    c3, c4, c5 = st.columns(3)
    for col, name, mime in ((c3, "promos.csv", "text/csv"), (c4, "promos.json", "application/json"),
                            (c5, "promos_report.md", "text/markdown")):
        if name in files:
            col.download_button(name, files[name], name, mime, width="stretch")
    reviewed = review[review.editor_verdict != "Not reviewed"]
    if len(reviewed):
        ok = reviewed.editor_verdict.str.contains("Post").sum()
        st.success(f"Reviewed {len(reviewed)} promos · {ok} marked 'Post it' → precision {ok / len(reviewed):.0%}")
    st.caption("Exports contain short screenplay quotes: share them only with the content owner.")

st.markdown('<div class="foot">PROMO FINDER STUDIO · transparent, reproducible ranking</div>', unsafe_allow_html=True)
