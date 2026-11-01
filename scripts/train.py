"""収集データ (npz) から行動分類MLPを学習する。

使い方: python3 train.py data/teacher.npz [data/dagger1.npz ...] --out models/policy.pt
"""
import argparse
import json

import numpy as np
import torch
import torch.nn as nn

from common import ACTIONS, PolicyMLP, scan_to_features, teacher_action


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data", nargs="+")
    ap.add_argument("--out", default="models/policy.pt")
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--relabel", action="store_true", help="生LiDAR値から現在の教師ルールで再ラベル付け")
    ap.add_argument("--sectors", type=int, default=24, help="特徴量のセクタ数 (24=15°刻み, 72=5°刻み)")
    ap.add_argument("--augment", type=int, default=0, help="ノイズ付き拡張の個数 (0なら拡張なし)")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    # 特徴量は保存してある生LiDAR値から毎回計算する（セクタ数を変えて実験できるように）
    raw = np.concatenate([np.load(p)["raw"] for p in args.data])
    X = np.stack([scan_to_features(r, args.sectors) for r in raw]).astype(np.float32)
    if args.relabel:
        # 現在の教師ルール(common.teacher_action)でラベルを付け直す
        y = np.array([teacher_action(r) for r in raw], dtype=np.int64)
        print("relabeled with", teacher_action.__name__)
    else:
        y = np.concatenate([np.load(p)["y"] for p in args.data]).astype(np.int64)
    print(f"samples={len(y)} label_counts={dict(zip(ACTIONS, np.bincount(y, minlength=3).tolist()))}")

    # 学習:検証 = 8:2 に分割
    idx = rng.permutation(len(y))
    n_val = int(len(y) * 0.2)
    va, tr = idx[:n_val], idx[n_val:]
    Xtr_np, ytr_np = X[tr], y[tr]
    if args.augment > 0:
        # データ拡張（学習側のみ。検証は元データのまま）:
        #   左右反転したスキャンと、距離ノイズ(σ=2cm)を加えたスキャンを作り、教師ルールで再ラベル
        assert args.relabel, "--augment は --relabel と併用する（拡張後のラベルを教師ルールで付けるため）"
        aug = []
        for r in raw[tr]:
            mirrored = np.roll(r[::-1], 1)          # 角度θ -> -θ
            aug.append(mirrored)
            for _ in range(args.augment):
                aug.append(np.clip(r + rng.normal(0, 0.02, r.shape), 0.0, 3.5).astype(np.float32))
                aug.append(np.clip(mirrored + rng.normal(0, 0.02, r.shape), 0.0, 3.5).astype(np.float32))
        Xa = np.stack([scan_to_features(r, args.sectors) for r in aug]).astype(np.float32)
        ya = np.array([teacher_action(r) for r in aug], dtype=np.int64)
        Xtr_np, ytr_np = np.concatenate([Xtr_np, Xa]), np.concatenate([ytr_np, ya])
        print(f"augmented train samples={len(ytr_np)}")
    Xtr, ytr = torch.tensor(Xtr_np), torch.tensor(ytr_np)
    Xva, yva = torch.tensor(X[va]), torch.tensor(y[va])

    # クラス不均衡（前進が多い）を損失の重みで補正
    counts = np.bincount(ytr_np, minlength=3).astype(np.float32)
    weight = torch.tensor(counts.sum() / (3 * np.maximum(counts, 1)))

    model = PolicyMLP(in_dim=args.sectors, hidden=args.hidden)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.CrossEntropyLoss(weight=weight)
    for ep in range(1, args.epochs + 1):
        model.train()
        perm = torch.randperm(len(ytr))
        for i in range(0, len(ytr), 128):
            b = perm[i:i + 128]
            opt.zero_grad()
            loss = loss_fn(model(Xtr[b]), ytr[b])
            loss.backward()
            opt.step()
        if ep % 50 == 0 or ep == args.epochs:
            model.eval()
            with torch.no_grad():
                tr_acc = (model(Xtr).argmax(1) == ytr).float().mean().item()
                va_acc = (model(Xva).argmax(1) == yva).float().mean().item()
            print(f"epoch {ep:4d} loss={loss.item():.4f} train_acc={tr_acc:.3f} val_acc={va_acc:.3f}")

    # 検証データの混同行列（行=教師ラベル, 列=モデル予測）
    with torch.no_grad():
        pred = model(Xva).argmax(1).numpy()
    cm = np.zeros((3, 3), dtype=int)
    for t, p in zip(yva.numpy(), pred):
        cm[t, p] += 1
    print("confusion matrix (rows=teacher, cols=model):", ACTIONS)
    print(cm)

    torch.save({"state_dict": model.state_dict(), "hidden": args.hidden, "n_sectors": args.sectors}, args.out)
    metrics = {"data": args.data, "relabel": args.relabel, "sectors": args.sectors, "augment": args.augment, "samples": int(len(y)), "val_acc": float(va_acc),
               "train_acc": float(tr_acc), "confusion_matrix": cm.tolist(), "actions": ACTIONS}
    with open(args.out.replace(".pt", "_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"saved -> {args.out}")


if __name__ == "__main__":
    main()
