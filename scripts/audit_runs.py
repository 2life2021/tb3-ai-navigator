"""評価ログ (logs/eval/run_*.csv) の事後分析: 初期位置・探索範囲・周回数・立ち往生を確認する。

- start_xy     : 最初の記録位置（全試行で同じ初期位置から始まったかの確認）
- cells_25cm   : 訪れた 0.25m 四方のマスの数（探索範囲の目安）
- laps         : 場の中心 (0,0) まわりの回転角 ÷ 360°（周回数の目安。符号は反時計回りが正）
- stuck_s      : 5秒間の移動量が 0.10m 未満だった時間の合計（立ち往生の目安）
- turn_ratio   : LEFT/RIGHT を選んだステップの割合

使い方: python3 scripts/audit_runs.py [logs/eval]
"""
import csv
import glob
import json
import math
import sys

import numpy as np

log_dir = sys.argv[1] if len(sys.argv) > 1 else "logs/eval"
print("| run | 条件 | start_xy | 距離[m] | 最接近[m] | 衝突 | cells_25cm | laps | stuck_s | turn_ratio |")
print("|---|---|---|---|---|---|---|---|---|---|")
for f in sorted(glob.glob(f"{log_dir}/run_*.csv")):
    s = json.load(open(f.replace(".csv", "_summary.json")))
    rows = [r for r in csv.DictReader(open(f)) if r["x"] not in ("", "None")]
    t = np.array([float(r["t"]) for r in rows])
    xy = np.array([[float(r["x"]), float(r["y"])] for r in rows])
    acts = [r["action"] for r in rows]
    cells = len(set(map(tuple, np.floor(xy / 0.25).astype(int))))
    ang = np.unwrap(np.arctan2(xy[:, 1], xy[:, 0]))
    laps = (ang[-1] - ang[0]) / (2 * math.pi)
    stuck = 0.0
    j = 0
    for i in range(len(t)):
        while t[i] - t[j] > 5.0:
            j += 1
        if t[i] - t[j] >= 4.5 and np.hypot(*(xy[i] - xy[j])) < 0.10:
            stuck += t[i] - t[i - 1] if i > 0 else 0.0
    turn = sum(a != "FORWARD" for a in acts) / len(acts)
    name = f.split("/")[-1].replace("run_", "").replace(".csv", "")
    print(f"| {name} | {s.get('tag')} | ({xy[0,0]:.2f}, {xy[0,1]:.2f}) | {s['distance_m']:.1f} | "
          f"{s['min_clearance_m']:.3f} | {s['collision_events']} | {cells} | {laps:+.2f} | {stuck:.1f} | {turn:.2f} |")
