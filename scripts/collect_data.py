"""Gazebo上で走行しながら学習データ (LiDAR特徴量, 教師ラベル) を収集するノード。

--policy teacher : 教師ルールで走行（ε確率でランダム行動を混ぜて状態を多様化）
--policy student : 学習済みモデルで走行し、その状態に対する教師ラベルを記録（DAgger）
どちらの場合も保存するラベルは常に「教師ルールの行動」である。
"""
import argparse
import os
import random
import time

import numpy as np
import rclpy
import torch
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from std_srvs.srv import Empty

from common import ACTION_TWIST, ACTIONS, clean_ranges, scan_to_features, teacher_action
from policy import load_policy

STUCK_DIST = 0.13   # これより近い障害物 = 衝突とみなしリセット


class Collector(Node):
    def __init__(self, args):
        super().__init__("ai_data_collector")
        self.args = args
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(LaserScan, "/scan", self.on_scan, qos_profile_sensor_data)
        self.create_subscription(Odometry, "/odom", self.on_odom, 10)
        self.reset_cli = self.create_client(Empty, "/reset_world")
        self.X, self.y, self.raw = [], [], []
        self.rand_action, self.rand_left = None, 0
        self.pos, self.last_move_pos, self.last_move_t = None, None, time.time()
        self.resets = 0
        self.cooldown_until = 0.0
        self.start = time.time()
        self.policy = load_policy(args.model) if args.policy == "student" else None
        self.get_logger().info(f"collecting: policy={args.policy}, duration={args.duration}s")

    def on_odom(self, msg):
        p = msg.pose.pose.position
        self.pos = (p.x, p.y)

    def reset_world(self, reason):
        self.resets += 1
        self.get_logger().warn(f"reset_world ({reason}), resets={self.resets}")
        self.pub.publish(Twist())
        if self.reset_cli.service_is_ready():
            self.reset_cli.call_async(Empty.Request())
        self.last_move_t = time.time()
        self.last_move_pos = None
        self.cooldown_until = time.time() + 2.0   # リセット直後の古いscanで再リセットしない

    def on_scan(self, msg):
        if time.time() - self.start > self.args.duration:
            self.pub.publish(Twist())
            raise SystemExit
        r = clean_ranges(msg.ranges)
        feat = scan_to_features(msg.ranges)
        label = teacher_action(msg.ranges)
        self.X.append(feat)
        self.y.append(label)
        self.raw.append(r)

        # 実際に実行する行動を選ぶ
        if self.rand_left > 0:
            act = self.rand_action
            self.rand_left -= 1
        elif random.random() < self.args.epsilon:
            self.rand_action, self.rand_left = random.randrange(3), random.randint(1, 4)
            act = self.rand_action
        elif self.policy is not None:
            act, _ = self.policy.predict_from_scan(msg.ranges)
            if random.random() < self.args.beta:   # DAgger: 確率betaで教師が操作
                act = label
        else:
            act = label

        v, w = ACTION_TWIST[act]
        tw = Twist()
        tw.linear.x, tw.angular.z = v, w
        self.pub.publish(tw)

        # 衝突・スタック検知 -> ワールドをリセット
        if time.time() < self.cooldown_until:
            pass
        elif r.min() < STUCK_DIST:
            self.reset_world(f"too close {r.min():.3f}m")
        elif self.pos is not None:
            if self.last_move_pos is None or np.hypot(self.pos[0] - self.last_move_pos[0],
                                                      self.pos[1] - self.last_move_pos[1]) > 0.10:
                self.last_move_pos, self.last_move_t = self.pos, time.time()
            elif time.time() - self.last_move_t > 15.0:
                self.reset_world("stuck")

        if len(self.y) % 100 == 0:
            counts = np.bincount(self.y, minlength=3)
            self.get_logger().info(f"samples={len(self.y)} label_counts={dict(zip(ACTIONS, counts.tolist()))}")

    def save(self):
        os.makedirs(os.path.dirname(self.args.out) or ".", exist_ok=True)
        np.savez_compressed(self.args.out, X=np.array(self.X), y=np.array(self.y),
                            raw=np.array(self.raw), resets=self.resets)
        self.get_logger().info(f"saved {len(self.y)} samples -> {self.args.out} (resets={self.resets})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", choices=["teacher", "student"], default="teacher")
    ap.add_argument("--model", default="models/policy.pt")
    ap.add_argument("--duration", type=float, default=300.0, help="収集時間 [s, 実時間]")
    ap.add_argument("--epsilon", type=float, default=0.10, help="ランダム行動の確率")
    ap.add_argument("--beta", type=float, default=0.0, help="DAgger時に教師が操作する確率")
    ap.add_argument("--out", default="data/teacher.npz")
    args = ap.parse_args()
    rclpy.init()
    node = Collector(args)
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
