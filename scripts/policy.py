"""学習済みモデルの読み込みと推論。"""
import numpy as np
import torch

from common import PolicyMLP, scan_to_features

torch.set_num_threads(1)   # 小さなMLPなので1スレッドで十分。Gazeboとのリソース競合を避ける


class Policy:
    def __init__(self, path):
        ckpt = torch.load(path, map_location="cpu")
        self.n_sectors = ckpt.get("n_sectors", 24)
        self.model = PolicyMLP(in_dim=self.n_sectors, hidden=ckpt["hidden"])
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()

    @torch.no_grad()
    def predict_from_scan(self, ranges):
        """LiDARの生データ(360本) -> (行動ID, 各行動の確率)"""
        feat = scan_to_features(ranges, self.n_sectors)
        x = torch.as_tensor(feat).unsqueeze(0)
        probs = torch.softmax(self.model(x), dim=1)[0].numpy()
        return int(probs.argmax()), probs


def load_policy(path):
    return Policy(path)
