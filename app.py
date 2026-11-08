"""Streamlit UI:  streamlit run app.py
Upload a .zip of episode screenplays -> ranked promos with hooks, cliffhangers and transcripts."""
import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from promo_finder.cli import run
from promo_finder.llm import PRESETS

st.set_page_config(page_title="Promo Finder", layout="wide")
st.title("Promo Finder — microdrama screenplays → ranked promo clips")

with st.sidebar:
    st.header("Model")
    provider = st.selectbox("LLM judge", ["none (rules only)"] + list(PRESETS) + ["mock"])
    provider = None if provider.startswith("none") else provider
    model = st.text_input("Model override", value="", help="Leave blank for the preset default")
    key = st.text_input("API key", type="password", help="Gemini / Groq free tiers work")
    judge_top = st.slider("Promos the LLM re-scores", 5, 80, 40)
    stitch = st.checkbox("Allow stitched (2-segment) promos", value=True)
    full_eval = st.checkbox("Run stability evaluation (slower)", value=False)

up = st.file_uploader("Episode screenplays (.zip of .txt files)", type=["zip"])
if up and st.button("Find promos", type="primary"):
    if key:
        os.environ["LLM_API_KEY"] = key
    tmp = Path(tempfile.mkdtemp())
    zp = tmp / "input.zip"
    zp.write_bytes(up.getvalue())
    logs = st.empty()
    lines = []

    def log(m):
        lines.append(str(m))
        logs.code("\n".join(lines[-12:]))

    with st.spinner("Scoring every legal cut point..."):
        recs, ev, audit, meta = run(str(zp), str(tmp / "out"), provider=provider, model=model or None,
                                    judge_top=judge_top, stitch=stitch, eval_extra=full_eval, log=log)
    st.session_state["res"] = (recs, ev, audit, meta, str(tmp / "out"))

if "res" in st.session_state:
    recs, ev, audit, meta, out = st.session_state["res"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Episodes", meta["episodes"])
    c2.metric("Promos found", len(recs))
    c3.metric("Episodes covered", ev["structural"]["episodes_covered"])
    c4.metric("Model", meta["model"])

    st.subheader("Post these first")
    slate = sorted([r for r in recs if r["post_first_slot"]], key=lambda r: r["post_first_slot"])
    seg = lambda r: " + ".join(f"E{s['episode']} {s['start']}–{s['end']}" for s in r["segments"])
    st.dataframe(pd.DataFrame([{"slot": r["post_first_slot"], "segments": seg(r), "sec": r["duration_s"],
                                "hook": r["hook"], "cliffhanger": r["cliffhanger"], "why": r["why"]} for r in slate]),
                 hide_index=True, width="stretch")

    st.subheader("All promos")
    ep_filter = st.multiselect("Filter by episode", sorted({e for r in recs for e in r["episodes"]}))
    for r in recs:
        if ep_filter and not set(ep_filter) & set(r["episodes"]):
            continue
        sc = r["scores"]
        with st.expander(f"#{r['rank']} · {seg(r)} · {r['duration_s']:.0f}s · score {sc['total']:.2f}"):
            st.markdown(f"**Hook:** {r['hook']}  \n**Cliffhanger:** {r['cliffhanger']}  \n**Why:** {r['why']}")
            st.caption(f"hook {sc.get('llm_hook', sc['hook'])} · cliff {sc.get('llm_cliff', sc['cliff'])} · "
                       f"standalone {sc.get('llm_standalone', sc['standalone'])} · body {sc['body']}")
            if r["llm_issues"]:
                st.warning("LLM flagged: " + ", ".join(map(str, r["llm_issues"])))
            st.code("\n".join(r["transcript"]))

    st.subheader("Quality checks")
    st.json(ev)
    with st.expander("Data-quality audit"):
        st.json({k: v for k, v in audit.items() if k != "issues"})
    for f in ("promos.csv", "promos.json", "promos_report.md", "review_sheet.csv"):
        st.download_button(f"Download {f}", Path(out, f).read_bytes(), file_name=f)
