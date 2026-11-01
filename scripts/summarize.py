"""logs/*_summary.json をタグごとに集計して表を出力する。

使い方: python3 scripts/summarize.py [logs]
"""
import glob
import json
import sys
from collections import defaultdict

import numpy as np

log_dir = sys.argv[1] if len(sys.argv) > 1 else "logs"
groups = defaultdict(list)
for f in sorted(glob.glob(f"{log_dir}/*_summary.json")):
    s = json.load(open(f))
    if s.get("tag"):
        groups[s["tag"]].append(s)

print("| 条件 | 試行 | 走行距離 [m] | 最接近距離 [m] (最小) | 衝突イベント (合計) | 教師一致率 |")
print("|---|---|---|---|---|---|")
for tag, runs in groups.items():
    d = np.array([r["distance_m"] for r in runs])
    c = np.array([r["min_clearance_m"] for r in runs])
    col = sum(r["collision_events"] for r in runs)
    a = np.array([r["agreement_with_teacher"] for r in runs])
    print(f"| {tag} | {len(runs)} | {d.mean():.1f} ± {d.std():.1f} | {c.mean():.3f} ({c.min():.3f}) | {col} | {a.mean():.2f} |")
