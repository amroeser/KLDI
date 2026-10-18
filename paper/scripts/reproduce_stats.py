"""Recompute the paper's statistics from the released CSV files.

Usage: python reproduce_stats.py [release_root]   (default: paper/ directory)

1. Recomputes KLDI from the texts wherever the texts are included and checks
   it against the stored scores (redacted rows are skipped in this check).
2. Recomputes threshold, Mann-Whitney U, ROC-AUC, Cliff's delta and bootstrap
   CIs from the stored scores.

Bootstrap CIs use a fixed seed here; the original run used an unseeded RNG,
so CI bounds can differ slightly from the paper.
"""
import csv, sys
from pathlib import Path

import numpy as np
from scipy.stats import mannwhitneyu
from sklearn.metrics import roc_auc_score

from kldi import kldi

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
read = lambda p: list(csv.DictReader(open(p, encoding="utf-8")))

src = {r["document_id"]: r["original_text"] for r in read(root / "data" / "source_passages.csv")}
par = {r["document_id"]: r["paraphrased_text"] for r in read(root / "data" / "selected_paraphrases.csv")}
hk_rows = read(root / "results" / "human_ai_scores.csv")
hh_rows = read(root / "data" / "human_human_pairs.csv")

hk = np.array([float(r["kldi"]) for r in hk_rows])
hh = np.array([float(r["kldi"]) for r in hh_rows])

# 1) verify stored scores against the texts where available
dev, checked = 0.0, 0
for r in hk_rows:
    a, b = src[r["document_id"]], par[r["document_id"]]
    if a and b:
        dev = max(dev, abs(kldi(a, b) - float(r["kldi"]))); checked += 1
print(f"Human->AI:    {len(hk)} pairs, recomputed {checked}, max |diff| = {dev:.2e}")
dev, checked = 0.0, 0
for r in hh_rows:
    a, b = src[r["document_id_a"]], src[r["document_id_b"]]
    if a and b:
        dev = max(dev, abs(kldi(a, b) - float(r["kldi"]))); checked += 1
print(f"Human->Human: {len(hh)} pairs, recomputed {checked}, max |diff| = {dev:.2e}")

# 2) statistics
q1, q3 = np.percentile(hh, [25, 75])
T = q3 + 1.5 * (q3 - q1)
labels = [0] * len(hh) + [1] * len(hk)
auc = roc_auc_score(labels, list(hh) + list(hk))
p = mannwhitneyu(hh, hk, alternative="two-sided").pvalue
cliff = (np.sum(hh[:, None] > hk[None, :]) - np.sum(hh[:, None] < hk[None, :])) / (len(hh) * len(hk))
rng = np.random.default_rng(42)
aucs, diffs = [], []
for _ in range(1000):
    a, b = rng.choice(hh, len(hh)), rng.choice(hk, len(hk))
    aucs.append(roc_auc_score(labels, list(a) + list(b)))
    diffs.append(np.median(b) - np.median(a))

print(f"T_adaptive (Q3 + 1.5*IQR of H->H): {T:.3f}")
print(f"H->AI above threshold: {int(np.sum(hk > T))} / {len(hk)}")
print(f"Mean KLDI  H->AI: {hk.mean():.3f}   H->H: {hh.mean():.3f}")
print(f"Median     H->AI: {np.median(hk):.3f}   H->H: {np.median(hh):.3f}")
print(f"Median diff (bootstrap): {np.median(diffs):.3f}  95% CI {np.percentile(diffs, [2.5, 97.5]).round(3)}")
print(f"Mann-Whitney U p: {p:.3e}")
print(f"ROC-AUC: {auc:.3f}  95% CI {np.percentile(aucs, [2.5, 97.5]).round(3)}   inverted: {1 - auc:.3f}")
print(f"Cliff's delta (H->H vs H->AI): {cliff:.3f}")
for d in sorted({r["domain"] for r in hk_rows}):
    v = np.array([float(r["kldi"]) for r in hk_rows if r["domain"] == d])
    print(f"  {d:8s} n={len(v):3d} mean={v.mean():.3f} above_T={int(np.sum(v > T))}")
