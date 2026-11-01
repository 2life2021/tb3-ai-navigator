"""学習済みMLPの推論結果だけで TurtleBot3 を自律走行させるノード。

/scan (LaserScan) -> 特徴量(72または24次元) -> MLP -> 行動確率 -> /cmd_vel (Twist)
行動確率は可視化用に /ai_nav/probs (Float32MultiArray: [P前進, P左, P右, v, w]) へも出力する。
走行中の評価指標（走行距離・最接近距離・衝突疑い回数）を記録し、終了時にCSV/JSONへ保存する。
"""
import argparse
import csv
import json
import os
import time

import numpy as np
import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from std_srvs.srv import Empty
from std_msgs.msg import Float32MultiArray

from common import ACTION_TWIST, ACTIONS, clean_ranges, teacher_action
from policy import load_policy

COLLISION_DIST = 0.13   # LiDAR中心からこれ未満 = 衝突（疑い）とみなす


class AIDriver(Node):
    def __init__(self, args):
        super().__init__("ai_driver")
        self.args = args
        self.policy = load_policy(args.model)
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.prob_pub = self.create_publisher(Float32MultiArray, "/ai_nav/probs", 10)   # 可視化用
        if args.reset:   # 評価条件を揃えるため、初期位置に戻してから走行開始（購読開始前に実行）
            self.pub.publish(Twist())
            cli = self.create_client(Empty, "/reset_world")
            if cli.wait_for_service(timeout_sec=5.0):
                rclpy.spin_until_future_complete(self, cli.call_async(Empty.Request()), timeout_sec=5.0)
                self.get_logger().info("reset_world done")
            time.sleep(1.0)
        self.create_subscription(LaserScan, "/scan", self.on_scan, qos_profile_sensor_data)
        self.create_subscription(Odometry, "/odom", self.on_odom, 10)
        self.start = time.time()
        self.pos, self.prev_pos = None, None
        self.distance = 0.0
        self.min_clear = float("inf")
        self.collisions, self.in_collision = 0, False
        self.steps, self.agree = 0, 0
        self.rows = []
        self.get_logger().info(f"AI driver started: model={args.model}")

    def on_odom(self, msg):
        p = msg.pose.pose.position
        self.pos = (p.x, p.y)
        if self.prev_pos is not None:
            d = np.hypot(p.x - self.prev_pos[0], p.y - self.prev_pos[1])
            if d < 0.5:   # reset_world 等によるジャンプは除外
                self.distance += d
        self.prev_pos = self.pos

    def on_scan(self, msg):
        if self.args.duration > 0 and time.time() - self.start > self.args.duration:
            raise SystemExit
        if self.args.driver == "ai":
            act, probs = self.policy.predict_from_scan(msg.ranges)   # ← 行動はAIの推論のみで決定
        else:   # 比較用ベースライン（教師ルールで走行）
            act = teacher_action(msg.ranges)
            probs = np.eye(3)[act]
        if self.args.control == "soft":
            # 確率で各行動の速度を重み付け平均: 迷っている(確率が割れている)ほど自動的に減速する
            v = float(sum(p * ACTION_TWIST[i][0] for i, p in enumerate(probs)))
            w = float(sum(p * ACTION_TWIST[i][1] for i, p in enumerate(probs)))
        else:   # argmax: 最も確率の高い行動をそのまま実行
            v, w = ACTION_TWIST[act]
        tw = Twist()
        tw.linear.x, tw.angular.z = v, w
        self.pub.publish(tw)
        self.prob_pub.publish(Float32MultiArray(data=[float(p) for p in probs] + [float(v), float(w)]))

        # ---- 以下は評価用の記録のみ（制御には使わない） ----
        r = clean_ranges(msg.ranges)
        rmin = float(r.min())
        self.min_clear = min(self.min_clear, rmin)
        if rmin < COLLISION_DIST and not self.in_collision:
            self.collisions += 1
        self.in_collision = rmin < COLLISION_DIST
        self.steps += 1
        self.agree += int(act == teacher_action(msg.ranges))
        t = time.time() - self.start
        self.rows.append([round(t, 2), ACTIONS[act], *np.round(probs, 3), round(rmin, 3),
                          *(np.round(self.pos, 3) if self.pos else (None, None))])
        if self.steps % 25 == 0:
            self.get_logger().info(
                f"t={t:5.1f}s act={ACTIONS[act]:7s} p={np.round(probs, 2)} min={rmin:.2f}m "
                f"dist={self.distance:.1f}m collisions={self.collisions}")

    def save(self):
        os.makedirs(self.args.log_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(self.args.log_dir, f"run_{stamp}.csv"), "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["t", "action", "p_forward", "p_left", "p_right", "min_range", "x", "y"])
            wr.writerows(self.rows)
        summary = {
            "tag": self.args.tag,
            "driver": self.args.driver,
            "control": self.args.control,
            "model": self.args.model if self.args.driver == "ai" else None,
            "duration_s": round(time.time() - self.start, 1),
            "steps": self.steps,
            "distance_m": round(self.distance, 2),
            "min_clearance_m": round(self.min_clear, 3),
            "collision_events": self.collisions,
            "agreement_with_teacher": round(self.agree / max(self.steps, 1), 3),
        }
        with open(os.path.join(self.args.log_dir, f"run_{stamp}_summary.json"), "w") as f:
            json.dump(summary, f, indent=2)
        self.get_logger().info(f"summary: {summary}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/policy.pt")
    ap.add_argument("--duration", type=float, default=0.0, help="走行時間 [s]、0なら無制限")
    ap.add_argument("--log-dir", default="logs")
    ap.add_argument("--tag", default="", help="評価集計用のラベル")
    ap.add_argument("--reset", action="store_true", help="開始時に /reset_world で初期位置へ戻す")
    ap.add_argument("--control", choices=["argmax", "soft"], default="argmax",
                    help="argmax: 最大確率の行動 / soft: 確率で速度を重み付け平均")
    ap.add_argument("--driver", choices=["ai", "teacher"], default="ai",
                    help="ai: MLPで走行 / teacher: 比較用に教師ルールで走行")
    args = ap.parse_args()
    rclpy.init()
    node = AIDriver(args)
    try:
        rclpy.spin(node)
    except (SystemExit, KeyboardInterrupt):
        pass
    finally:
        node.pub.publish(Twist())
        node.save()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
