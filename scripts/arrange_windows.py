"""デモ撮影用に VNC 画面のウィンドウを自動で並べる（プロセスは終了させない）。

- ターミナル類を最小化する
- Gazebo を画面右側に配置する（左側は AI視点モニター用に空ける）
使い方: DISPLAY=:0 python3 scripts/arrange_windows.py [--list]
"""
import sys

from Xlib import X, Xatom, display, protocol

d = display.Display()
root = d.screen().root
SW, SH = d.screen().width_in_pixels, d.screen().height_in_pixels
TOP = 28            # 上部パネルの高さ
BOTTOM = 24         # 下部パネルの高さ
LEFT_W = 400        # AI視点モニターの幅


def atom(name):
    return d.intern_atom(name)


def name_of(w):
    p = w.get_full_property(atom("_NET_WM_NAME"), atom("UTF8_STRING"))
    if p:
        return p.value.decode("utf-8", "replace")
    return w.get_wm_name() or ""


def wm_class(w):
    try:
        c = w.get_wm_class()
        return c[1] if c else ""
    except Exception:
        return ""


def send(w, msg_type, data):
    ev = protocol.event.ClientMessage(window=w, client_type=atom(msg_type), data=(32, (data + [0] * 5)[:5]))
    root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)


def clients():
    p = root.get_full_property(atom("_NET_CLIENT_LIST"), Xatom.WINDOW)
    return [d.create_resource_object("window", wid) for wid in (p.value if p else [])]


def minimize(w):
    send(w, "WM_CHANGE_STATE", [3])   # IconicState


def unmaximize(w):
    send(w, "_NET_WM_STATE", [0, atom("_NET_WM_STATE_MAXIMIZED_VERT"), atom("_NET_WM_STATE_MAXIMIZED_HORZ"), 1])


def move_resize(w, x, y, width, height):
    # flags: gravity=static(10) | x | y | w | h
    send(w, "_NET_MOVERESIZE_WINDOW", [10 | (1 << 8) | (1 << 9) | (1 << 10) | (1 << 11), x, y, width, height])


def activate(w):
    send(w, "_NET_ACTIVE_WINDOW", [2, X.CurrentTime, 0])


ws = clients()
for w in ws:
    print(f"0x{w.id:x}  class={wm_class(w)!r:22} name={name_of(w)!r}")
if "--list" in sys.argv:
    sys.exit(0)

for w in ws:
    cls, nm = wm_class(w).lower(), name_of(w)
    if "terminal" in cls or "terminator" in cls:   # ターミナルのみ（デスクトップ等は触らない）
        minimize(w)
        print("minimized:", nm)
    elif nm == "Gazebo" or "gazebo" in cls:
        unmaximize(w)
        move_resize(w, LEFT_W, TOP, SW - LEFT_W, SH - TOP - BOTTOM)
        activate(w)
        print("placed Gazebo:", (LEFT_W, TOP, SW - LEFT_W, SH - TOP - BOTTOM))
d.sync()
