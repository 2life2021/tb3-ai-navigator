"""一括評価 (logs/eval) の結果を、条件ごとの点で表示する（各点 = 1試行）。

初期位置が (-2.0, -0.5) でなかった試行（/reset_world が効かなかった回）は白抜きで示す。
使い方: python3 scripts/plot_eval.py [logs/eval] [--out figs/eval.png]
"""
import argparse
import csv
import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

INK, INK2, GRID, BLUE = "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"

ap = argparse.ArgumentParser()
ap.add_argument("log_dir", nargs="?", default="logs/eval")
ap.add_argument("--out", default="figs/eval.png")
args = ap.parse_args()

runs = []
for f in sorted(glob.glob(f"{args.log_dir}/run_*_summary.json")):
    s = json.load(open(f))
    first = next(r for r in csv.DictReader(open(f.replace("_summary.json", ".csv"))) if r["x"] not in ("", "None"))
    s["reset_ok"] = abs(float(first["x"]) + 2.0) < 0.1 and abs(float(first["y"]) + 0.5) < 0.1
    runs.append(s)
tags = list(dict.fromkeys(r["tag"] for r in runs))

fig, axes = plt.subplots(1, 2, figsize=(11, 3.4), facecolor="#fcfcfb")
for ax, key, label in [(axes[0], "min_clearance_m", "min LiDAR range during run [m]  (higher = safer)"),
                       (axes[1], "distance_m", "distance traveled in 90 s [m]")]:
    for i, tag in enumerate(tags):
        rs = [r for r in runs if r["tag"] == tag]
        for j, r in enumerate(rs):
            y = len(tags) - 1 - i + (j - 1) * 0.12
            ax.scatter(r[key], y, s=60, color=BLUE if r["reset_ok"] else "white",
                       edgecolor=BLUE, linewidth=2, zorder=3)
    if key == "min_clearance_m":
        ax.axvline(0.13, color="#d03b3b", linestyle="--", linewidth=1)
        ax.annotate("collision\nthreshold", (0.13, len(tags) - 0.6), xytext=(4, 0),
                    textcoords="offset points", color="#d03b3b", fontsize=8, va="top")
        ax.set_xlim(0.1, 0.34)
    ax.set_yticks(range(len(tags)))
    ax.set_yticklabels(tags[::-1] if key == "min_clearance_m" else [""] * len(tags))
    ax.set_ylim(-0.6, len(tags) - 0.4)
    ax.set_xlabel(label, color=INK2)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9, left=False)
    ax.grid(axis="x", color=GRID)
    ax.set_axisbelow(True)
axes[0].scatter([], [], s=60, color=BLUE, label="started from reset pose")
axes[0].scatter([], [], s=60, color="white", edgecolor=BLUE, linewidth=2, label="reset failed (different start)")
axes[0].legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(0, -0.22), ncol=2)
fig.suptitle("Batch evaluation: 4 conditions x 3 runs (90 s each, collision events = 0 in all runs)",
             x=0.01, ha="left", fontsize=11, color=INK)
os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
fig.savefig(args.out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
print("saved", args.out)
