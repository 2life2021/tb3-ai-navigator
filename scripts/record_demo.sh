#!/bin/bash
# コンテナの画面(:0, Gazebo + AI視点モニター)を ffmpeg で録画する。
# 使い方: bash scripts/record_demo.sh [秒数=150] [出力=video/demo.mp4]
# X の認証ファイルは XAUTHORITY で指定する（既定: /home/ubuntu/.Xauthority）
set -e
cd "$(dirname "$0")/.."
DUR=${1:-150}; OUT=${2:-video/demo.mp4}
export DISPLAY=:0 XAUTHORITY=${XAUTHORITY:-/home/ubuntu/.Xauthority}
mkdir -p "$(dirname "$OUT")"
SIZE=$(DISPLAY=:0 xdpyinfo | awk '/dimensions/{print $2}')
DISPLAY=:0 ffmpeg -y -loglevel error -f x11grab -video_size "$SIZE" -framerate 15 -i :0 \
  -t "$DUR" -vf "crop=trunc(iw/2)*2:trunc(ih/2)*2" -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p "$OUT"
echo "saved $OUT"
