"""デモ撮影用: Gazebo の左パネルを閉じ、3D表示をズームして、マウスカーソルを画面端に退避する。

XTEST で入力をシミュレートするだけで、Gazebo の設定やプロセスには触れない。
使い方: DISPLAY=:0 python3 scripts/gazebo_view.py SPLIT_X SPLIT_Y [ZOOM_X ZOOM_Y STEPS]
  SPLIT_X, SPLIT_Y : 左パネルと3D表示の境界（スプリッタ）の座標。左端へドラッグして閉じる
  ZOOM_X, ZOOM_Y   : ズームの中心にする画面座標。STEPS>0 で縮小（ホイール下）、<0 で拡大
"""
import sys
import time

from Xlib import X, display
from Xlib.ext import xtest

d = display.Display()


def move(x, y):
    xtest.fake_input(d, X.MotionNotify, x=x, y=y)
    d.sync()
    time.sleep(0.05)


def drag(x0, y0, x1, y1):
    move(x0, y0)
    xtest.fake_input(d, X.ButtonPress, 1)
    d.sync()
    for i in range(1, 21):
        move(int(x0 + (x1 - x0) * i / 20), int(y0 + (y1 - y0) * i / 20))
    xtest.fake_input(d, X.ButtonRelease, 1)
    d.sync()


def scroll(x, y, steps):
    move(x, y)
    button = 5 if steps > 0 else 4
    for _ in range(abs(steps)):
        xtest.fake_input(d, X.ButtonPress, button)
        xtest.fake_input(d, X.ButtonRelease, button)
        d.sync()
        time.sleep(0.15)


args = [int(a) for a in sys.argv[1:]]
if len(args) >= 2 and args[0] > 0:
    drag(args[0], args[1], 402, args[1])
if len(args) >= 5 and args[4] != 0:
    scroll(args[2], args[3], args[4])
move(d.screen().width_in_pixels - 1, d.screen().height_in_pixels // 2)   # カーソル退避
