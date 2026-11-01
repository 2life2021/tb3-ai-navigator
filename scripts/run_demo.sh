#!/bin/bash
# デモ動画の撮影: AI視点モニター + AI走行 + 画面録画 をまとめて実行する（Gazebo起動済みであること）
# 使い方: bash scripts/run_demo.sh [走行秒数=150] [モデル=models/policy_v2_aug.pt] [追加オプション...]
# 例:     bash scripts/run_demo.sh 150 models/policy_v2_aug.pt --control soft
# ※ ai_driver と ai_monitor は同じユーザーで実行すること（FastDDS の共有メモリ通信がユーザー間で失敗するため）
cd "$(dirname "$0")/.."
DUR=${1:-150}; MODEL=${2:-models/policy_v2_aug.pt}; shift $(( $# < 2 ? $# : 2 ))
export DISPLAY=:0 XAUTHORITY=${XAUTHORITY:-/home/ubuntu/.Xauthority}
mkdir -p video
python3 scripts/ai_monitor.py > video/monitor.log 2>&1 &
MON=$!
sleep 3
bash scripts/record_demo.sh $((DUR + 5)) video/demo.mp4 &
REC=$!
python3 scripts/ai_driver.py --model "$MODEL" --reset --duration "$DUR" --log-dir logs/demo "$@"
wait $REC
kill -INT $MON 2>/dev/null
echo "done: video/demo.mp4, logs/demo/"
