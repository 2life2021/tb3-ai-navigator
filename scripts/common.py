"""共通処理: LiDAR特徴量の抽出、行動の定義、教師ルール、モデル定義。"""
import math

import numpy as np
import torch
import torch.nn as nn

RANGE_MAX = 3.5          # TurtleBot3 LDS の最大計測距離 [m]
N_SECTORS = 24           # 360度を15度ずつ24セクタに分割
FEATURE_DIM = N_SECTORS

# 行動（分類クラス）と、それに対応する速度指令 (v [m/s], w [rad/s])
ACTIONS = ["FORWARD", "LEFT", "RIGHT"]
ACTION_TWIST = {
    0: (0.18, 0.0),    # 前進
    1: (0.02, 0.9),    # 左旋回（ほぼその場旋回）
    2: (0.02, -0.9),   # 右旋回
}


def clean_ranges(ranges):
    """inf / nan / 0 を最大距離に置き換え、[0, RANGE_MAX] にクリップする。"""
    r = np.asarray(ranges, dtype=np.float32)
    r = np.where(np.isfinite(r) & (r > 0.0), r, RANGE_MAX)
    return np.clip(r, 0.0, RANGE_MAX)


def scan_to_features(ranges, n_sectors=N_SECTORS):
    """360本のLiDARを n_sectors 個のセクタの最小距離に圧縮し、0〜1に正規化する。

    24セクタ(15°, v1): セクタ0 = 正面(-7.5°〜+7.5°)
    72セクタ(5°, v2) : セクタ0 = 0°〜5°（境界が5°の倍数になり、教師ルールの角度と揃う）
    インデックスが増えるほど反時計回り(左)。/scan は angle_min=0 (正面) から反時計回りに約1°刻み。
    """
    r = clean_ranges(ranges)
    n = len(r)
    angles = np.arange(n) * (2.0 * math.pi / n)
    deg = np.degrees(angles)
    width = 360.0 / n_sectors
    offset = width / 2.0 if n_sectors == 24 else 0.0
    sector = (((deg + offset) % 360.0) // width).astype(int) % n_sectors
    feat = np.full(n_sectors, RANGE_MAX, dtype=np.float32)
    np.minimum.at(feat, sector, r)
    return feat / RANGE_MAX


def _deg_slice(r, start_deg, end_deg):
    """角度範囲[start, end] (度, 反時計回り, 負は右) のレンジを取り出す。"""
    n = len(r)
    idx = [int(round(d * n / 360.0)) % n for d in range(start_deg, end_deg + 1)]
    return r[idx]


def teacher_action_v1(ranges):
    """教師ルール v1（models/policy.pt, policy_dagger1.pt の学習に使用）。

    - 前方±25°が0.55m以上空き、斜め前(25〜60°)も0.30m以上空いていれば前進
    - そうでなければ、左右(20〜100°)の平均的な空間が広い方へ旋回
    """
    r = clean_ranges(ranges)
    front = _deg_slice(r, -25, 25).min()
    fl = _deg_slice(r, 25, 60).min()
    fr = _deg_slice(r, -60, -25).min()
    if front > 0.55 and fl > 0.30 and fr > 0.30:
        return 0
    left_space = _deg_slice(r, 20, 100).mean()
    right_space = _deg_slice(r, -100, -20).mean()
    return 1 if left_space >= right_space else 2


def teacher_action_v2(ranges):
    """教師ルール v2: v1 に「真横の壁との距離」の確認を追加。

    v1 は真横を見ないため、壁すれすれの前進や、壁際での旋回時に車体が擦れることがあった。
    - 前方±30°が0.55m以上、斜め前(30〜75°)が0.35m以上空いていること
    - さらに真横(75〜105°)が0.22m未満なら、その壁から離れる方向へ旋回
    - それ以外で前方が塞がっていれば、左右(20〜100°)の空間が広い方へ旋回
    """
    r = clean_ranges(ranges)
    front = _deg_slice(r, -30, 30).min()
    fl, fr = _deg_slice(r, 30, 75).min(), _deg_slice(r, -75, -30).min()
    sl, sr = _deg_slice(r, 75, 105).min(), _deg_slice(r, -105, -75).min()
    if front > 0.55 and fl > 0.35 and fr > 0.35:
        if sl < 0.22 and sl <= sr:
            return 2
        if sr < 0.22:
            return 1
        return 0
    left_space = _deg_slice(r, 20, 100).mean()
    right_space = _deg_slice(r, -100, -20).mean()
    return 1 if left_space >= right_space else 2


# 学習ラベル生成に使う教師（※ 学習データの正解ラベルはこのルールで自動生成している）
teacher_action = teacher_action_v2


class PolicyMLP(nn.Module):
    """LiDAR特徴量(24次元) -> 行動3クラスのロジットを出す多層パーセプトロン。"""

    def __init__(self, in_dim=FEATURE_DIM, hidden=64, n_actions=len(ACTIONS)):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, n_actions),
        )

    def forward(self, x):
        return self.net(x)
