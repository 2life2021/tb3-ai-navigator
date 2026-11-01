"""走行ログ (logs/run_*.csv) から、レポート用の図を作る。

1. 軌跡（AIが選んだ行動で色分け）
2. 行動確率の時系列（AIの出力）と LiDAR 最小距離

使い方: python3 scripts/plot_run.py logs/eval/run_XXXX.csv [--out figs/run.png] [--tmax 60]
"""
import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

COLORS = {"FORWARD": "#2a78d6", "LEFT": "#eb6834", "RIGHT": "#1baf7a"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--out", default="figs/run.png")
    ap.add_argument("--tmax", type=float, default=60.0, help="確率の時系列を描く時間幅 [s]")
    args = ap.parse_args()

    rows = [r for r in csv.DictReader(open(args.csv)) if r["x"] not in ("", "None")]
    t = np.array([float(r["t"]) for r in rows])
    xy = np.array([[float(r["x"]), float(r["y"])] for r in rows])
    act = np.array([r["action"] for r in rows])
    P = np.array([[float(r["p_forward"]), float(r["p_left"]), float(r["p_right"])] for r in rows])
    rmin = np.array([float(r["min_range"]) for r in rows])

    plt.rcParams.update({"font.size": 10, "text.color": INK, "axes.labelcolor": INK2})
    fig = plt.figure(figsize=(12, 5), facecolor="#fcfcfb")
    gs = fig.add_gridspec(2, 2, width_ratios=[1, 1.4], height_ratios=[2, 1], wspace=0.25, hspace=0.15)

    # 1. 軌跡
    ax = fig.add_subplot(gs[:, 0])
    ax.plot(xy[:, 0], xy[:, 1], color=GRID, linewidth=2, zorder=1)
    for name, c in COLORS.items():
        m = act == name
        ax.scatter(xy[m, 0], xy[m, 1], s=10, color=c, label=name, zorder=2, linewidths=0)
    ax.scatter(*xy[0], s=80, marker="o", facecolor="white", edgecolor=INK, linewidth=2, zorder=3)
    ax.annotate("start", xy[0], xytext=(8, -12), textcoords="offset points", color=INK2, fontsize=9)
    ax.set_aspect("equal")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title("Trajectory (colored by AI action)", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0, -0.16), ncol=3)
    style(ax)

    # 2. 行動確率（積み上げ）
    m = t <= t[0] + args.tmax
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.stackplot(t[m], P[m].T, colors=list(COLORS.values()), labels=list(COLORS.keys()),
                  edgecolor="#fcfcfb", linewidth=0.5)
    ax2.set_ylim(0, 1)
    ax2.set_xlim(t[m][0], t[m][-1])
    ax2.set_ylabel("MLP output\nprobability")
    ax2.set_title("AI output over time (softmax probabilities)", loc="left", fontsize=11)
    ax2.legend(frameon=False, fontsize=9, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.08))
    ax2.tick_params(labelbottom=False)
    style(ax2)

    # 3. LiDAR最小距離
    ax3 = fig.add_subplot(gs[1, 1], sharex=ax2)
    ax3.plot(t[m], rmin[m], color=INK2, linewidth=2)
    ax3.axhline(0.13, color="#d03b3b", linewidth=1, linestyle="--")
    ax3.annotate("collision threshold 0.13 m", (t[m][0], 0.13), xytext=(4, 3),
                 textcoords="offset points", color="#d03b3b", fontsize=8)
    ax3.set_ylim(0, max(1.0, rmin[m].max() * 1.05))
    ax3.set_xlabel("time [s]")
    ax3.set_ylabel("min LiDAR\nrange [m]")
    style(ax3)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig.savefig(args.out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print("saved", args.out)


if __name__ == "__main__":
    main()
