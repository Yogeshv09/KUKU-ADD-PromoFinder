"""Quality checks that need no hand labels.

1. Structural validity  — every promo 20-60s, cuts on legal shot boundaries, never mid-line.
2. Silver cliffhanger test — the writers end every episode on a cliffhanger, so a working cliff
   detector should rate each episode's final beat near the top of all possible end points.
   Run with the writers' explicit markers ("cliffhanger", "cut to black", "ominous"...) switched OFF,
   otherwise the test is circular.
3. Weight stability — perturb the scoring weights +-30% and check the top-10 barely changes.
"""
from __future__ import annotations

import random
from statistics import mean, median

from . import candidates as C
from .parser import Episode


def structural(promos, idx_by_ep):
    bad_len, bad_cut, n = [], [], 0
    for i, p in enumerate(promos, 1):
        n += 1
        if not (C.MIN_LEN - 0.01 <= p.duration <= C.MAX_LEN + 0.01):
            bad_len.append(i)
        for s in p.segments:
            ix = idx_by_ep[s.ep]
            if not (ix._clean(s.start) and ix._clean(s.end)):
                bad_cut.append(i)
    covered = sorted({s.ep for p in promos for s in p.segments})
    return {"promos": n, "duration_violations": bad_len, "mid_line_cuts": bad_cut,
            "episodes_covered": len(covered), "episodes_without_promo": sorted(set(idx_by_ep) - set(covered)),
            "continuous": sum(len(p.segments) == 1 for p in promos),
            "stitched": sum(len(p.segments) > 1 for p in promos),
            "mean_duration_s": round(mean(p.duration for p in promos), 1)}


def silver_cliff(eps: list[Episode], protagonist: str):
    """Reported on all episodes and on odd episodes only: the cliff lexicon was tuned while reading
    even-numbered episode endings, so odd episodes act as a held-out set."""
    res = {}
    for split, keep in (("all", lambda n: True), ("held_out_odd", lambda n: n % 2 == 1 and n != 1)):
        res[split] = _silver(eps, protagonist, keep)
    return res


def _silver(eps, protagonist, keep):
    res = {}
    for markers in (False, True):
        pct = []
        for ep in eps:
            if not keep(ep.ep):
                continue
            ix = C.EpisodeIndex(ep, protagonist, use_markers=markers)
            ends = [t for t in ix.ends if t >= C.MIN_LEN]
            if len(ends) < 3:
                continue
            final = max(ends)
            # the last cut point is often a 1s 'cut to black' tail: take the best of the final 3s
            final_score = max(ix.cliff_at[t][0] for t in ends if t >= final - 3.0)
            all_scores = sorted((ix.cliff_at[t][0] for t in ends), reverse=True)
            rank = sum(1 for s in all_scores if s > final_score)
            pct.append(1 - rank / len(all_scores))
        res["with_markers" if markers else "markers_off"] = {
            "episodes": len(pct), "median_percentile": round(median(pct), 3), "mean_percentile": round(mean(pct), 3),
            "share_in_top_20pct": round(sum(p >= 0.8 for p in pct) / len(pct), 3),
            "random_baseline_share_in_top_20pct": 0.2}
    return res


def stability(eps, trials=20, seed=7):
    base = dict(C.WEIGHTS)
    ref, _, _ = C.find_candidates(eps)
    key = lambda p: tuple((s.ep, round(s.start), round(s.end)) for s in p.segments)
    ref10 = {key(p) for p in ref[:10]}
    ref_eps = {p.first_ep for p in ref[:10]}
    rng = random.Random(seed)
    j_exact, j_ep = [], []
    try:
        for _ in range(trials):
            for k in base:
                C.WEIGHTS[k] = base[k] * rng.uniform(0.7, 1.3)
            got, _, _ = C.find_candidates(eps)
            g10 = {key(p) for p in got[:10]}
            j_exact.append(len(ref10 & g10) / len(ref10 | g10))
            g_eps = {p.first_ep for p in got[:10]}
            j_ep.append(len(ref_eps & g_eps) / len(ref_eps | g_eps))
    finally:
        C.WEIGHTS.update(base)
    return {"trials": trials, "top10_exact_jaccard_mean": round(mean(j_exact), 3),
            "top10_episode_jaccard_mean": round(mean(j_ep), 3)}
