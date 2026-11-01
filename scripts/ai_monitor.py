"""AI視点モニター: LiDAR点群と、MLPが出した行動確率をリアルタイム表示する（動画・デモ用）。

/scan と /ai_nav/probs (ai_driver.py が出力) を購読して OpenCV ウィンドウに描画する。
制御には一切関与しない。
"""
import math

import cv2
import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Float32MultiArray

from common import ACTIONS, RANGE_MAX, clean_ranges, scan_to_features

W, H = 400, 540
SCALE = 50            # px / m
CX, CY = W // 2, 200  # ロボット位置（画面上）
# BGR
COL = {"FORWARD": (214, 120, 42), "LEFT": (52, 104, 235), "RIGHT": (122, 175, 27)}
BG, INK, INK2, GRID = (251, 252, 252), (11, 11, 11), (78, 81, 82), (223, 227, 228)


class Monitor(Node):
    def __init__(self):
        super().__init__("ai_monitor")
        self.ranges, self.probs, self.vw = None, None, (0.0, 0.0)
        self.placed = False
        self.create_subscription(LaserScan, "/scan", self.on_scan, qos_profile_sensor_data)
        self.create_subscription(Float32MultiArray, "/ai_nav/probs", self.on_probs, 10)
        self.create_timer(0.1, self.draw)

    def on_scan(self, msg):
        self.ranges = np.asarray(msg.ranges, dtype=np.float32)

    def on_probs(self, msg):
        self.probs = np.array(msg.data[:3])
        self.vw = (msg.data[3], msg.data[4])

    def draw(self):
        img = np.full((H, W, 3), BG, np.uint8)
        cv2.putText(img, "AI view: LiDAR -> MLP -> action", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, INK, 1, cv2.LINE_AA)
        if self.ranges is not None:
            r = clean_ranges(self.ranges)
            n = len(r)
            # 72セクタ特徴量（MLPの入力）を扇形の濃淡で表示: 近いほど濃い
            feat = scan_to_features(self.ranges, 72)
            for i, f in enumerate(feat):
                a0, a1 = i * 5.0, (i + 1) * 5.0
                d = f * RANGE_MAX
                shade = int(150 + 90 * min(d, 2.0) / 2.0)
                pts = [(CX, CY)] + [(int(CX - d * SCALE * math.sin(math.radians(a))),
                                     int(CY - d * SCALE * math.cos(math.radians(a)))) for a in np.linspace(a0, a1, 4)]
                cv2.fillPoly(img, [np.array(pts, np.int32)], (shade, shade, shade - 10))
        for rr in (0.5, 1.0, 2.0, 3.0):   # 距離リング（扇形の上に描く）
            cv2.circle(img, (CX, CY), int(rr * SCALE), GRID, 1, cv2.LINE_AA)
            cv2.putText(img, f"{rr:.1f}m", (CX + 3, CY - int(rr * SCALE) + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, INK2, 1, cv2.LINE_AA)
        if self.ranges is not None:
            r = clean_ranges(self.ranges)
            n = len(r)
            # 生LiDAR点
            for k in range(n):
                if not np.isfinite(self.ranges[k]):
                    continue
                a = 2 * math.pi * k / n
                x = int(CX - r[k] * SCALE * math.sin(a))   # 左 = 画面左
                y = int(CY - r[k] * SCALE * math.cos(a))   # 前 = 画面上
                cv2.circle(img, (x, y), 2, INK, -1, cv2.LINE_AA)
        # ロボット
        cv2.circle(img, (CX, CY), 7, INK, -1, cv2.LINE_AA)
        cv2.arrowedLine(img, (CX, CY), (CX, CY - 22), INK, 2, cv2.LINE_AA, tipLength=0.4)

        # 行動確率バー
        y0 = 385
        cv2.putText(img, "MLP output (probability)", (12, y0 - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, INK, 1, cv2.LINE_AA)
        if self.probs is not None:
            best = int(np.argmax(self.probs))
            for i, (name, p) in enumerate(zip(ACTIONS, self.probs)):
                y = y0 + i * 30
                cv2.putText(img, name, (12, y + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, INK if i == best else INK2,
                            2 if i == best else 1, cv2.LINE_AA)
                cv2.rectangle(img, (100, y + 4), (100 + 230, y + 24), GRID, -1)
                cv2.rectangle(img, (100, y + 4), (100 + int(230 * p), y + 24), COL[name], -1)
                cv2.putText(img, f"{p:.2f}", (340, y + 19), cv2.FONT_HERSHEY_SIMPLEX, 0.5, INK, 1, cv2.LINE_AA)
            v, w = self.vw
            cv2.putText(img, f"cmd_vel: v={v:.2f} m/s  w={w:+.2f} rad/s", (12, y0 + 3 * 30 + 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, INK, 1, cv2.LINE_AA)
        else:
            cv2.putText(img, "waiting for /ai_nav/probs ...", (12, y0 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, INK2, 1, cv2.LINE_AA)
        cv2.imshow("AI view", img)
        if not self.placed:   # 画面左上に配置
            cv2.moveWindow("AI view", 0, 30)
            self.placed = True
        cv2.waitKey(1)


def main():
    rclpy.init()
    node = Monitor()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        cv2.destroyAllWindows()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
