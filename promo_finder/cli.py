"""Command-line entry point.

  python -m promo_finder.cli --input path/to/show_folder_or.zip --out raw_outputs
  LLM_PROVIDER=gemini GEMINI_API_KEY=... python -m promo_finder.cli --input show.zip --out raw_outputs_gemini
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import tempfile
import time
import zipfile
from pathlib import Path

from .audit import audit_show
from .candidates import find_candidates, WEIGHTS
from .evaluate import silver_cliff, stability, structural
from .judge import judge
from .llm import LLM
from .parser import load_show
from .report import rank_for_posting, to_records, write_outputs


def resolve_input(path: str) -> Path:
    p = Path(path)
    if p.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="promo_in_"))
        with zipfile.ZipFile(p) as z:
            z.extractall(tmp)
        return tmp
    return p


def run(input_path, out, provider=None, model=None, base_url=None, judge_top=40, stitch=True,
        per_episode=3, eval_extra=True, log=print):
    t0 = time.time()
    folder = resolve_input(input_path)
    eps = load_show(folder)
    if not eps:
        raise SystemExit(f"No episodes parsed from {input_path}")
    show = next((d.name for d in Path(folder).rglob("*") if d.is_dir()), Path(input_path).stem)
    log(f"Parsed {len(eps)} episodes ({sum(len(e.events) for e in eps)} timed events) from '{show}'")

    audit = audit_show(eps)
    log(f"Data quality: {audit['issue_counts']}")

    promos, idx, protagonist = find_candidates(eps, stitch=stitch, per_episode=per_episode)
    idx_by_ep = {ix.ep.ep: ix for ix in idx}
    log(f"Rules stage: {len(promos)} non-overlapping promos (protagonist detected: {protagonist})")

    llm = LLM(provider, model, base_url)
    if llm.enabled:
        log(f"LLM judge: {llm.describe()} on top {judge_top}")
        promos = judge(promos, idx_by_ep, {e.ep: e for e in eps}, llm, top=judge_top, log=log)

    order, slate = rank_for_posting(promos, max(e.ep for e in eps))
    promos = sorted(promos, key=lambda p: -p.total)
    recs = to_records(promos, slate)

    out = Path(out)
    ev = {"structural": structural(promos, idx_by_ep)}
    if eval_extra:
        ev["silver_cliffhanger_test"] = silver_cliff(eps, protagonist)
        ev["weight_stability"] = stability(eps)
    meta = {"show": show, "episodes": len(eps), "model": llm.describe(), "weights": WEIGHTS,
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "runtime_s": round(time.time() - t0, 1), "llm_calls": llm.calls,
            "llm_tokens_in": llm.tokens_in, "llm_tokens_out": llm.tokens_out, "stitching": stitch}
    write_outputs(out, recs, slate, meta)
    (out / "data_quality.json").write_text(json.dumps(audit, indent=1))
    (out / "evaluation.json").write_text(json.dumps(ev, indent=1))
    log(f"Evaluation: {json.dumps(ev)}")
    log(f"Wrote {out}/ in {meta['runtime_s']}s")
    return recs, ev, audit, meta


def main():
    ap = argparse.ArgumentParser(description="Find promo clips in timed microdrama screenplays.")
    ap.add_argument("--input", required=True, help="folder of episode .txt files, or a .zip of them")
    ap.add_argument("--out", default="raw_outputs")
    ap.add_argument("--provider", default=None,
                    help="none | gemini | groq | openrouter | ollama | openai | anthropic | mock (env LLM_PROVIDER)")
    ap.add_argument("--model", default=None, help="override model name (env LLM_MODEL)")
    ap.add_argument("--base-url", default=None, help="override endpoint (env LLM_BASE_URL)")
    ap.add_argument("--judge-top", type=int, default=40, help="how many shortlisted promos the LLM re-scores")
    ap.add_argument("--no-stitch", action="store_true", help="only continuous single-stretch promos")
    ap.add_argument("--per-episode", type=int, default=3)
    ap.add_argument("--fast", action="store_true", help="skip the slower stability evaluation")
    a = ap.parse_args()
    run(a.input, a.out, a.provider, a.model, a.base_url, a.judge_top, not a.no_stitch, a.per_episode,
        eval_extra=not a.fast)


if __name__ == "__main__":
    main()
