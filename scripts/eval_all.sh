#!/bin/bash
# 各条件を N 回ずつ、初期位置から DURATION 秒走らせて評価する（Gazebo起動済みであること）
cd "$(dirname "$0")/.."
N=${N:-3}; DURATION=${DURATION:-90}
run() { tag=$1; shift; for i in $(seq 1 $N); do
  python3 scripts/ai_driver.py --reset --duration $DURATION --tag "$tag" --log-dir logs/eval "$@" 2>&1 | grep summary; done; }
run "teacher_v2 (rule)"      --driver teacher
run "v1 BC (argmax)"         --model models/policy.pt
run "v2 aug (argmax)"        --model models/policy_v2_aug.pt
run "v2 aug (soft)"          --model models/policy_v2_aug.pt --control soft
python3 scripts/summarize.py logs/eval
