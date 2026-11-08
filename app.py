"""Promo Finder Studio — Streamlit UI for the promo_finder engine.

Run:  streamlit run app.py
Upload a .zip (or .txt files) of timed episode screenplays -> ranked 20-60 s promo clips.
No screenplay is stored: every run uses a temporary folder that is deleted afterwards.
"""
import html
import io
import json
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

# --------------------------------------------------------------------------- styling
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700;800&display=swap');
:root{--bg:#090c17;--panel:#11162a;--panel2:#161d36;--line:#262f4d;--ink:#eef1fb;--muted:#9aa4c2;
      --pink:#10e39a;--amber:#c6f36b;--teal:#5cc8ff;--grad:linear-gradient(100deg,#10e39a,#c6f36b);}
html,body,[class*="css"],.stApp{font-family:'Inter',sans-serif;}
.stApp{background:radial-gradient(1100px 500px at 85% -10%,rgba(16,227,154,.14),transparent 60%),
       radial-gradient(900px 500px at -10% 10%,rgba(92,200,255,.07),transparent 60%),var(--bg);color:var(--ink);}
[data-testid="stSidebar"]{background:#0d1222;border-right:1px solid var(--line);}
[data-testid="stHeader"]{background:rgba(9,12,23,.7);backdrop-filter:blur(8px);}
.block-container{padding-top:1.6rem;max-width:1320px;}
h1,h2,h3,h4{font-family:'Space Grotesk',sans-serif;letter-spacing:-.02em;}
#MainMenu,footer{visibility:hidden;}
.hero{position:relative;overflow:hidden;padding:34px 38px;border-radius:24px;border:1px solid #1f3d33;
      background:linear-gradient(120deg,#0f241d 0%,#10192b 55%,#0f2230 100%);margin-bottom:22px;}
.hero:after{content:"";position:absolute;right:-60px;top:-60px;width:260px;height:260px;border-radius:50%;
      background:var(--grad);opacity:.18;filter:blur(30px);}
.hero .eyebrow{font-size:.72rem;letter-spacing:.22em;font-weight:800;text-transform:uppercase;
      background:var(--grad);-webkit-background-clip:text;color:transparent;}
.hero h1{font-size:2.9rem;line-height:1.05;margin:10px 0 10px;color:#fff;}
.hero h1 span{background:var(--grad);-webkit-background-clip:text;color:transparent;}
.hero p{color:#c3cae0;font-size:1.02rem;max-width:760px;line-height:1.6;margin:0;}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px;}
.chip{font-size:.74rem;font-weight:700;border:1px solid #3a4468;border-radius:999px;padding:6px 12px;color:#d6dcf0;
      background:rgba(255,255,255,.03);}
.kicker{color:var(--muted);letter-spacing:.14em;text-transform:uppercase;font-size:.72rem;font-weight:800;margin:6px 0 4px;}
.metric{border:1px solid var(--line);background:linear-gradient(160deg,var(--panel2),var(--panel));border-radius:18px;
        padding:16px 18px;min-height:104px;}
.metric .l{color:var(--muted);font-size:.74rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;}
.metric .v{font-family:'Space Grotesk';font-size:2rem;font-weight:700;color:#fff;margin-top:4px;line-height:1.1;}
.metric .s{color:#7f89a8;font-size:.75rem;margin-top:2px;}
.card{position:relative;border:1px solid var(--line);border-radius:20px;padding:20px 22px 16px 92px;margin-bottom:12px;
      background:linear-gradient(110deg,#161c35,#10152a);}
.card.top{border-color:#1f5a44;box-shadow:0 0 0 1px rgba(16,227,154,.15),0 10px 40px -20px rgba(16,227,154,.45);}
.rank{position:absolute;left:20px;top:18px;width:54px;height:54px;border-radius:16px;display:flex;align-items:center;
      justify-content:center;font-family:'Space Grotesk';font-weight:700;font-size:1.45rem;color:#04130d;background:var(--grad);}
.rank.dim{background:#232b4a;color:#cfd6ee;}
.meta{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:10px;}
.tag{font-size:.72rem;font-weight:700;border-radius:8px;padding:4px 9px;background:#1f2745;color:#cdd5f0;border:1px solid #2c3660;}
.tag.time{background:rgba(92,200,255,.1);color:#a8e1ff;border-color:#24527a;}
.tag.cat{background:rgba(198,243,107,.1);color:#dcf7a6;border-color:#4f6b25;}
.tag.score{background:rgba(16,227,154,.12);color:#8cf5cb;border-color:#1f6b4f;}
.beat{display:grid;grid-template-columns:86px 1fr;gap:10px;align-items:start;margin:6px 0;}
.beat .lab{font-size:.66rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;padding:5px 0;border-radius:7px;
      text-align:center;}
.beat .lab.h{background:rgba(16,227,154,.15);color:#7ef2c4;}
.beat .lab.c{background:rgba(198,243,107,.14);color:#d7f59a;}
.beat .txt{color:#f2f4fb;font-size:.98rem;line-height:1.45;}
.why{color:#aab3cf;font-size:.86rem;margin-top:8px;line-height:1.5;}
.bars{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:12px;}
.bar .n{display:flex;justify-content:space-between;font-size:.7rem;color:var(--muted);font-weight:700;margin-bottom:4px;}
.bar .t{height:7px;border-radius:9px;background:#222a48;overflow:hidden;}
.bar .f{height:100%;border-radius:9px;background:var(--grad);}
.script{border:1px solid var(--line);border-radius:14px;background:#0c1020;padding:10px 14px;}
.line{display:grid;grid-template-columns:110px 1fr;gap:10px;padding:4px 0;border-bottom:1px dashed #1c2340;font-size:.88rem;}
.line:last-child{border-bottom:0;}
.line .ts{font-family:'Space Grotesk';color:#a8e1ff;font-size:.78rem;padding-top:1px;}
.line .sp{color:#c6f36b;font-weight:700;}
.line .act{color:#9aa4c2;font-style:italic;}
.ok{color:#10e39a;font-weight:700;} .bad{color:#ff6b8f;font-weight:700;}
.empty{border:1px dashed #33406a;border-radius:20px;padding:26px;background:rgba(255,255,255,.02);}
.step{border:1px solid var(--line);border-radius:18px;padding:18px;background:var(--panel);height:100%;}
.step b{font-family:'Space Grotesk';font-size:1.05rem;color:#fff;} .step p{color:var(--muted);font-size:.86rem;margin:.4rem 0 0;}
.step .num{font-family:'Space Grotesk';font-size:.8rem;font-weight:700;background:var(--grad);-webkit-background-clip:text;color:transparent;}
.foot{text-align:center;color:#69728f;font-size:.78rem;margin-top:36px;}
[data-testid="stTabs"] button p{font-weight:700;font-size:.95rem;}
.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"]{background:var(--grad)!important;color:#04130d!important;
      border:0!important;font-weight:800!important;border-radius:12px!important;}
.stButton>button,.stDownloadButton>button{border-radius:12px!important;}
/* dark fallbacks (in case .streamlit/config.toml is missing) */
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] span,[data-testid="stSidebar"] h2,
[data-testid="stWidgetLabel"] p,[data-testid="stMarkdownContainer"] h3,[data-testid="stCaptionContainer"]{color:#dfe4f5;}
[data-testid="stCaptionContainer"]{color:#8d97b5!important;}
.stButton>button:not([kind="primary"]),.stDownloadButton>button:not([kind="primary"]){background:#161d36!important;
      color:#e9edf8!important;border:1px solid #2f3a62!important;}
[data-testid="stFileUploaderDropzone"]{background:#121831!important;border:1px dashed #3a4570!important;}
[data-testid="stExpander"] details{background:#0f1428;border:1px solid #262f4d;border-radius:14px;}
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
            f'<span class="tag cat">{E(r["category"])}</span>', f'<span class="tag">{E(r["type"])}</span>',
            f'<span class="tag score">★ {r["scores"]["total"]:.2f}</span>']
    if r.get("described_by") and r["described_by"] != "rules":
        tags.append(f'<span class="tag">AI: {E(r["described_by"])}</span>')
    return (f'<div class="card {"top" if top else ""}"><div class="rank {"" if top else "dim"}">{num}</div>'
            f'<div class="meta">{"".join(tags)}</div>'
            f'<div class="beat"><div class="lab h">▶ Hook</div><div class="txt">{E(r["hook"])}</div></div>'
            f'<div class="beat"><div class="lab c">⏸ Cliff</div><div class="txt">{E(r["cliffhanger"])}</div></div>'
            f'<div class="why">💡 {E(r["why"])}</div>{bars(r)}</div>')


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


def metric(label, value, sub=""):
    st.markdown(f'<div class="metric"><div class="l">{E(label)}</div><div class="v">{E(value)}</div>'
                f'<div class="s">{E(sub)}</div></div>', unsafe_allow_html=True)


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


# --------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("## 🎬 Promo Finder Studio")
    st.caption("SCREENPLAY → RANKED PROMO CLIPS")
    st.markdown('<div class="kicker">01 · Input</div>', unsafe_allow_html=True)
    uploads = st.file_uploader("Screenplays (.zip or .txt files)", type=["zip", "txt"], accept_multiple_files=True)
    go = st.button("⚡ Find promos", type="primary", disabled=not uploads, width="stretch")
    demo = st.button("▶ Try the demo show (fictional)", width="stretch")

    st.markdown('<div class="kicker">02 · AI judge (optional)</div>', unsafe_allow_html=True)
    choice = st.selectbox("Model", ["Rules only (free, no key)", "gemini", "groq", "openrouter", "openai", "anthropic"])
    provider = None if choice.startswith("Rules") else choice
    model = key = ""
    judge_top = 20
    if provider:
        default_model = "gemini-flash-latest" if provider == "gemini" else PRESETS[provider][2]
        model = st.text_input("Model name", value=default_model)
        env_name = PRESETS[provider][3]
        has_secret = bool(env_name and os.getenv(env_name))
        key = st.text_input("API key", type="password",
                            placeholder="saved in app secrets" if has_secret else "paste key, then press Enter",
                            help="Used for this run only, never stored.")
        judge_top = st.slider("Promos the AI re-scores", 5, 60, 15, step=5,
                              help="Free tiers allow a few calls per minute: ~6 s per promo.")
    st.markdown('<div class="kicker">03 · Options</div>', unsafe_allow_html=True)
    stitch = st.toggle("Allow 2-segment (stitched) promos", value=True)
    full_eval = st.toggle("Run stability test (+~60 s)", value=False)
    if st.button("↺ Clear results", width="stretch"):
        for k in list(st.session_state):
            del st.session_state[k]
        st.rerun()
    st.divider()
    st.caption("🔒 Files are processed in a temporary folder and deleted after each run. "
               "Upload only scripts you are allowed to process.")


def need_key():
    if not provider or key:
        return False
    env_name = PRESETS[provider][3]
    return not (env_name and os.getenv(env_name)) and not os.getenv("LLM_API_KEY")


# --------------------------------------------------------------------------- hero
st.markdown("""
<div class="hero">
  <div class="eyebrow">✦ Kuku · AI Generalist · Problem 1</div>
  <h1>Find the moment.<br><span>Make them watch.</span></h1>
  <p>Drop in a season of timed microdrama screenplays. Promo Finder scans every legal cut, scores the first
  3 seconds and the final beat, and hands your editor a ranked shortlist of 20–60 s promos — with timestamps,
  the hook, the cliffhanger and why each one works.</p>
  <div class="chips"><span class="chip">⚡ Hook in 3 s</span><span class="chip">⏸ Cliffhanger endings</span>
  <span class="chip">✂ Cuts on shot boundaries, never mid-line</span><span class="chip">🧠 Optional AI judge</span>
  <span class="chip">⇩ CSV · JSON · review sheet</span></div>
</div>""", unsafe_allow_html=True)

if go or demo:
    if need_key():
        st.error("Paste an API key in the sidebar (and press Enter), or choose **Rules only**.")
    else:
        try:
            if demo:
                res = analyse([("demo.zip", demo_zip_bytes())], "The Lighthouse Heir (fictional demo)",
                              provider, model, key, judge_top, stitch, full_eval)
            else:
                res = analyse([(f.name, f.getvalue()) for f in uploads], ", ".join(f.name for f in uploads[:2]),
                              provider, model, key, judge_top, stitch, full_eval)
            for k in [k for k in st.session_state if k.startswith(("v_", "n_"))]:
                del st.session_state[k]
            st.session_state["res"] = res
            st.toast(f"Found {len(res['recs'])} promos", icon="🎬")
        except (ValueError, zipfile.BadZipFile, SystemExit) as ex:
            st.error(f"Could not read the screenplays: {ex}")
        except Exception as ex:  # keep the UI alive and show what went wrong
            st.error(f"Analysis failed: {type(ex).__name__}: {ex}")

res = st.session_state.get("res")

# --------------------------------------------------------------------------- empty state
if not res:
    st.markdown('<div class="kicker">How it works</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    steps = [("01", "Parse", "Screenplay → timed shots, actions, sound and dialogue with delivery tags."),
             ("02", "Find legal cuts", "Only camera-shot boundaries that never split a spoken line."),
             ("03", "Score every window", "Hook (first 3 s) · cliffhanger · standalone · intensity, 0–10 each."),
             ("04", "Rank & review", "Diverse 'post first' slate; editors approve or reject each clip.")]
    for c, (n, t, d) in zip(cols, steps):
        c.markdown(f'<div class="step"><div class="num">{n}</div><b>{t}</b><p>{d}</p></div>', unsafe_allow_html=True)
    st.write("")
    a, b = st.columns([1.4, 1])
    with a:
        st.markdown('<div class="empty"><h3 style="margin-top:0">Start in 10 seconds</h3>'
                    '<p style="color:#aab3cf">Upload your show in the sidebar and press <b>Find promos</b> — or press '
                    '<b>Try the demo show</b> to see it on a short fictional drama.</p></div>', unsafe_allow_html=True)
    with b:
        st.markdown('<div class="empty"><h3 style="margin-top:0">Expected format</h3>'
                    '<p style="color:#aab3cf">One <code>.txt</code> per episode with blocks like '
                    '<code>**NAME (Delivery):**</code> then <code>Start: (00:04.80) | End: (00:07.10)</code>.</p></div>',
                    unsafe_allow_html=True)
        st.download_button("⇩ Download the demo screenplays", demo_zip_bytes(), "lighthouse_heir_demo.zip",
                           "application/zip", width="stretch")
    st.markdown('<div class="foot">PROMO FINDER STUDIO · built for Kuku editors · transparent, reproducible ranking</div>',
                unsafe_allow_html=True)
    st.stop()

# --------------------------------------------------------------------------- dashboard
recs, ev, audit, meta, files = res["recs"], res["ev"], res["audit"], res["meta"], res["files"]
s = ev["structural"]
slate = sorted([r for r in recs if r.get("post_first_slot")], key=lambda r: r["post_first_slot"])

st.markdown(f'<div class="kicker">Run · {E(meta.get("source", meta["show"]))} · model: {E(meta["model"])}</div>',
            unsafe_allow_html=True)
m = st.columns(5)
with m[0]: metric("Episodes", meta["episodes"], f"{audit['total_runtime_min']} min of story")
with m[1]: metric("Promos found", len(recs), f"{s['continuous']} continuous · {s['stitched']} stitched")
with m[2]: metric("Coverage", f"{s['episodes_covered']}/{meta['episodes']}", "episodes with a promo")
with m[3]: metric("Avg length", f"{s['mean_duration_s']} s", "all within 20–60 s")
with m[4]: metric("Clean cuts", "100%" if not s["mid_line_cuts"] else f"{len(s['mid_line_cuts'])} issues",
                  "no cut inside a spoken line")
st.write("")

t1, t2, t3, t4, t5 = st.tabs(["🔥 Post these first", "🎬 All promos", "🗺️ Promo map", "🧪 Quality", "⇩ Exports"])

# ---- tab 1: slate
with t1:
    st.markdown("### The posting slate")
    st.caption("Best quality × earliest in the funnel, max one per episode and three per hook type. "
               "Earlier episodes land new viewers at the start of the show and spoil less.")
    if not slate:
        st.info("No slate for this run.")
    for r in slate:
        st.markdown(card(r, slot=r["post_first_slot"]), unsafe_allow_html=True)
        with st.expander(f"📜 Script for slot #{r['post_first_slot']} · {seg_label(r)}"):
            st.markdown(script_html(r["transcript"]), unsafe_allow_html=True)

# ---- tab 2: all promos with filters + editor review
with t2:
    f1, f2, f3, f4 = st.columns([1.4, 1, 1, 1])
    q = f1.text_input("Search hook / cliffhanger / why", placeholder="e.g. poison, duke, slap")
    eps = sorted({e for r in recs for e in r["episodes"]})
    ep_sel = f2.multiselect("Episodes", eps)
    cats = sorted({r["category"] for r in recs})
    cat_sel = f3.multiselect("Hook type", cats)
    sort = f4.selectbox("Sort by", ["Quality rank", "Episode order", "Hook score", "Cliffhanger score", "Shortest first"])
    view = [r for r in recs
            if (not q or q.lower() in f"{r['hook']} {r['cliffhanger']} {r['why']}".lower())
            and (not ep_sel or set(ep_sel) & set(r["episodes"]))
            and (not cat_sel or r["category"] in cat_sel)]
    keyf = {"Quality rank": lambda r: r["rank"], "Episode order": lambda r: (r["episodes"][0], r["segments"][0]["start_s"]),
            "Hook score": lambda r: -score(r, "hook"), "Cliffhanger score": lambda r: -score(r, "cliff"),
            "Shortest first": lambda r: r["duration_s"]}[sort]
    view.sort(key=keyf)
    n_view = len(view)
    opts = sorted({o for o in (10, 20, 50) if o < n_view} | {n_view}) if n_view else [0]
    show_n = st.select_slider("Show", options=opts, value=min(20, n_view) if n_view else 0,
                              format_func=lambda v: f"all {v}" if v == n_view else str(v)) if len(opts) > 1 else n_view
    st.caption(f"Showing {min(show_n, n_view)} of {n_view} matching promos ({len(recs)} total)")
    if not view:
        st.info("No promos match these filters.")
    for r in view[:show_n]:
        st.markdown(card(r), unsafe_allow_html=True)
        with st.expander(f"📜 Script, review & details · #{r['rank']}"):
            st.markdown(script_html(r["transcript"]), unsafe_allow_html=True)
            c1, c2 = st.columns([1, 2])
            c1.selectbox("Editor verdict", ["Not reviewed", "✅ Post it", "✂ Needs a trim", "❌ Reject"], key=f"v_{r['rank']}")
            c2.text_input("Notes (better start/end, issues…)", key=f"n_{r['rank']}")
            if r.get("llm_issues"):
                st.warning("AI flagged: " + ", ".join(map(str, r["llm_issues"])))
            if r.get("llm_notes"):
                st.caption(" · ".join(map(str, r["llm_notes"])))

# ---- tab 3: promo map
with t3:
    st.markdown("### Where the promos live")
    st.caption("Each row is an episode; coloured bars are promo windows (brighter = higher score). Hover for the hook.")
    rows = []
    for r in recs:
        for sgm in r["segments"]:
            rows.append({"Episode": f"E{sgm['episode']:02d}", "start": sgm["start_s"], "end": sgm["end_s"],
                         "Score": r["scores"]["total"], "Rank": r["rank"], "Hook": r["hook"][:90],
                         "Clip": seg_label(r)})
    dur = pd.DataFrame([{"Episode": f"E{p['ep']:02d}", "start": 0.0, "end": p["duration_s"]} for p in audit["per_episode"]])
    try:
        import altair as alt
        base = alt.Chart(dur).mark_bar(color="#1c2442", cornerRadius=4).encode(
            y=alt.Y("Episode:N", sort=None, title=None), x=alt.X("start:Q", title="seconds into episode"), x2="end:Q")
        bars_ = alt.Chart(pd.DataFrame(rows)).mark_bar(cornerRadius=4, opacity=.95).encode(
            y=alt.Y("Episode:N", sort=None), x="start:Q", x2="end:Q",
            color=alt.Color("Score:Q", scale=alt.Scale(range=["#1d4d3c", "#10e39a", "#c6f36b"]), legend=None),
            tooltip=["Rank", "Clip", "Score", "Hook"])
        chart = (base + bars_).properties(height=max(160, 16 * len(dur)), background="transparent").configure_view(strokeWidth=0).configure_axis(
            labelColor="#9aa4c2", titleColor="#9aa4c2", gridColor="#1a2140", domainColor="#262f4d")
        st.altair_chart(chart, width="stretch")
    except Exception:
        st.bar_chart(pd.DataFrame(rows).groupby("Episode").size())
    a, b = st.columns(2)
    with a:
        st.markdown("**Promos by hook type**")
        st.bar_chart(pd.Series([r["category"] for r in recs]).value_counts(), color="#10e39a")
    with b:
        st.markdown("**Promo length (seconds)**")
        st.bar_chart(pd.cut(pd.Series([r["duration_s"] for r in recs]), [20, 25, 30, 35, 40, 45, 50, 55, 60],
                            include_lowest=True).value_counts().sort_index().rename(index=str), color="#c6f36b")

# ---- tab 4: quality
with t4:
    st.markdown("### Quality checks")
    checks = [("Every promo is 20–60 s", not s["duration_violations"]),
              ("No cut inside a spoken line", not s["mid_line_cuts"]),
              ("Every episode has at least one promo", not s["episodes_without_promo"]),
              ("Hook, cliffhanger and why filled for every promo", all(r["hook"] and r["cliffhanger"] and r["why"] for r in recs)),
              ("No missing episode numbers", not audit["missing_episode_numbers"])]
    st.markdown("".join(f'<div style="margin:4px 0">{"<span class=ok>✔ PASS</span>" if ok else "<span class=bad>✖ FAIL</span>"}'
                        f'&nbsp;&nbsp;{E(lbl)}</div>' for lbl, ok in checks), unsafe_allow_html=True)
    sil = ev.get("silver_cliffhanger_test")
    if sil:
        st.markdown("**Silver cliffhanger test** — is each episode's written ending ranked in the top 20 % of possible end points? "
                    "(random = 20 %; held-out = odd episodes not used for tuning)")
        st.dataframe(pd.DataFrame([{"Episodes": split, "Writer cue words": "off" if mk == "markers_off" else "on",
                                    "In top 20 %": f"{v['share_in_top_20pct']:.0%}", "Median percentile": v["median_percentile"]}
                                   for split, d in sil.items() for mk, v in d.items()]), hide_index=True, width="stretch")
    stab = ev.get("weight_stability")
    if stab:
        st.markdown(f"**Weight stability** (±30 % random weights, {stab['trials']} trials): top-10 overlap "
                    f"**{stab['top10_exact_jaccard_mean']:.2f}** exact clips · **{stab['top10_episode_jaccard_mean']:.2f}** same episodes")
    if not sil and not stab:
        st.caption("Turn on **Run stability test** in the sidebar for the silver cliffhanger and stability checks.")
    st.markdown("**Data-quality audit**")
    ic = audit.get("issue_counts", {})
    names = {"dialogue_silence_gt_8s": "Dialogue-free stretches > 8 s", "dialogue_overlap": "Overlapping lines (two speakers)",
             "very_long_event": "Very long single block (> 15 s)", "scene_gap": "Gaps between scenes",
             "outside_scene_bounds": "Events outside their scene", "negative_duration": "Negative durations",
             "empty_text": "Empty blocks"}
    if ic:
        st.dataframe(pd.DataFrame([{"Check": names.get(k, k), "Count": v} for k, v in ic.items()]), hide_index=True, width="stretch")
    else:
        st.success("No data-quality issues found.")
    with st.expander("Per-episode stats"):
        st.dataframe(pd.DataFrame(audit["per_episode"]), hide_index=True, width="stretch")
    st.warning("Scores are editorial heuristics, not predicted views or retention. Check the first 3 s and the final beat "
               "against the actual footage before publishing.")

# ---- tab 5: exports
with t5:
    st.markdown("### Download the run")
    review = pd.DataFrame([{"rank": r["rank"], "post_first_slot": r.get("post_first_slot") or "", "clip": seg_label(r, " "),
                            "duration_s": r["duration_s"], "hook": r["hook"], "cliffhanger": r["cliffhanger"],
                            "score": r["scores"]["total"],
                            "editor_verdict": st.session_state.get(f"v_{r['rank']}", "Not reviewed"),
                            "editor_notes": st.session_state.get(f"n_{r['rank']}", "")} for r in recs])
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
        z.writestr("editor_review.csv", review.to_csv(index=False))
    c1, c2 = st.columns(2)
    c1.download_button("⇩ Everything (zip)", zbuf.getvalue(), "promo_finder_outputs.zip", "application/zip",
                       type="primary", width="stretch")
    c2.download_button("⇩ Editor review sheet (with your verdicts)", review.to_csv(index=False).encode("utf-8-sig"),
                       "editor_review.csv", "text/csv", width="stretch")
    c3, c4, c5 = st.columns(3)
    for col, name, mime in ((c3, "promos.csv", "text/csv"), (c4, "promos.json", "application/json"),
                            (c5, "promos_report.md", "text/markdown")):
        if name in files:
            col.download_button(f"⇩ {name}", files[name], name, mime, width="stretch")
    reviewed = review[review.editor_verdict != "Not reviewed"]
    if len(reviewed):
        ok = reviewed.editor_verdict.str.contains("Post").sum()
        st.success(f"Reviewed {len(reviewed)} promos · {ok} marked 'Post it' → precision {ok / len(reviewed):.0%}")
    st.caption("Exports contain short screenplay quotes — share them only with the content owner.")

st.markdown('<div class="foot">PROMO FINDER STUDIO · built for Kuku editors · transparent, reproducible ranking</div>',
            unsafe_allow_html=True)
