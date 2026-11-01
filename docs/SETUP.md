# 環境構築 — コンテナの起動から AI 走行まで

本作品を開発・評価したときの環境を、その手順どおりに再構築するための手引きです。記載内容は、開発に使ったコンテナの設定・起動スクリプト・環境変数から確認したものです。**まっさらな PC で、この手順を最初から通して試したことはありません**（下の「未検証の点」を参照）。

---

## 1. 全体の構成

```
Windows 11（ホスト）
 └─ Docker（Linux コンテナを実行。開発時の Docker Engine 29.8.2）
     └─ コンテナ pai_ros2（イメージ airobotbook/ros2-desktop-ai-robot-book-humble）
         ├─ Ubuntu 22.04.5 / ROS 2 Humble / Gazebo 11.10.2 / Python 3.10.12
         ├─ PyTorch 2.6.0・numpy・OpenCV・matplotlib（イメージに同梱）
         ├─ VNC デスクトップ（MATE）→ ブラウザから noVNC で表示（http://localhost:6080）
         ├─ ~/airobot_ws : TurtleBot3 のシミュレーションパッケージ（ソースからビルド済み）
         └─ /workspace   : ホストのディレクトリをマウント（本リポジトリを置く場所）
```

- GPU は使いません（PyTorch は CPU で動かします）。
- 本作品のために `pip install` や `apt install` をしたものは**ありません**。必要なものはすべてイメージに入っています。

---

## 2. 必要なもの

| 項目 | 内容 |
|---|---|
| Docker | Docker Desktop（Windows）など、Linux コンテナを動かせるもの |
| ディスク | イメージだけで約 25 GB |
| メモリ | 開発時のコンテナから見えていたメモリは約 7.7 GB |
| ブラウザ | noVNC でコンテナのデスクトップを表示するため |

---

## 3. コンテナの起動

開発時は、次の内容のスクリプト（`run_pai_container.sh`）を、マウントしたいディレクトリで実行してコンテナを作りました。

```bash
docker run -d --name pai_ros2 \
  -p 6080:80 --shm-size=512m \
  -p 9090:9090 -p 9876:9876 \
  -v "$(pwd)":/workspace \
  airobotbook/ros2-desktop-ai-robot-book-humble:latest
```

- `-p 6080:80`: ブラウザで http://localhost:6080 を開くと、コンテナのデスクトップ（noVNC）が表示されます。
- `--shm-size=512m`: 共有メモリのサイズです（Gazebo や DDS が使います）。
- `-v "$(pwd)":/workspace`: 実行したディレクトリが、コンテナの `/workspace` になります。
- 9090、9876 番ポートは書籍の環境の設定で、本作品では使っていません。
- **イメージを固定する場合**: `:latest` は更新される可能性があります。開発時のイメージは次のとおりです（2025-02-12 作成）。
  ```
  airobotbook/ros2-desktop-ai-robot-book-humble@sha256:b58ec74c019aacd9ce4818fa25fc5a9e0a1f22f8c9cd1f5260994bf15cd9eb63
  ```

すでにコンテナがある場合は、作り直さずに `docker start pai_ros2` で起動します。

---

## 4. コードの配置

```bash
# コンテナ内（noVNC のターミナル、または docker exec）で
cd /workspace
git clone https://github.com/2life2021/tb3-ai-navigator.git
cd tb3-ai-navigator
```

> 開発時は、Windows 側のフォルダを正本とし、`sync_to_container.ps1` / `sync_from_container.ps1`（`docker cp` による同期）でコンテナの `/workspace/tb3_ai_nav` とやり取りしていました。コンテナが消えても成果物が残るようにするためです。新しく構築する場合は、上の `git clone` で十分です。

ライブラリがそろっているかの確認:
```bash
python3 -c "import torch, numpy, cv2, matplotlib; print(torch.__version__, numpy.__version__, cv2.__version__, matplotlib.__version__)"
# 開発時: 2.6.0+cu124 1.24.4 4.5.4 3.5.1
```

---

## 5. シミュレーションの起動

noVNC のデスクトップでターミナルを開き、次を実行します。

```bash
export TURTLEBOT3_MODEL=burger      # ← 必須
ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py
```

- **このコンテナの `~/.bashrc` では `TURTLEBOT3_MODEL=happy_mini` が既定値**になっています。`burger` を指定し忘れると、別のロボットが出てきます。
- 開発時の Gazebo は、このターミナルの環境（`.bashrc` で `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`）で起動していました（起動中のプロセスの環境変数で確認済み）。
- 使用した `turtlebot3_gazebo` は、`~/airobot_ws` にある AI-Robot-Book-Humble/turtlebot3_happy_mini（コミット 80f775a、`turtlebot3_gazebo` 2.2.6）のものです。ロボットは (-2.0, -0.5) に出現します。

起動の確認（別のターミナルで）:
```bash
ros2 topic list | grep -E "^/(scan|cmd_vel|odom)$"   # 3つとも表示されること
ros2 topic hz /scan                                   # 約 5Hz
ros2 topic info -v /cmd_vel                           # 送信元に teleop_keyboard がないこと（下記の注意を参照）
ros2 topic hz /cmd_vel                                # AI を起動する前は、何も流れていないこと
```

---

## 6. AI 走行の実行

```bash
cd /workspace/tb3-ai-navigator
python3 scripts/ai_driver.py --model models/policy_v2_aug.pt --reset
# Ctrl+C で停止。--duration 120 で120秒後に自動停止。--control soft で soft 制御
```

- **`teleop_keyboard` が起動していたら止めてください**。キーを押していなくても `/cmd_vel` にゼロ速度を 10Hz で送り続け、AI の指令と競合します。
- 開発時、本作品のノード（`ai_driver.py` など）は、ホストから `docker exec pai_ros2 bash -lc "source /opt/ros/humble/setup.bash; ..."` で起動しました。この方法では `.bashrc` が読まれないため、RMW は既定の FastDDS でした。Gazebo（CycloneDDS）との通信は正常でした。noVNC のターミナルから起動すると、全ノードが CycloneDDS になります（この組み合わせでは評価していません）。
- 本作品のノードが使うのは、ROS 2 の標準メッセージ（`sensor_msgs`、`geometry_msgs`、`nav_msgs`、`std_msgs`、`std_srvs`）だけです。TurtleBot3 のパッケージを import する必要はありません。

### AI 視点モニターとデモ撮影（任意）
```bash
python3 scripts/ai_monitor.py                 # ai_driver と同じユーザーで起動すること
bash scripts/run_demo.sh 150                  # モニター + 走行 + ffmpeg 録画 → video/demo.mp4
```
- `docker exec`（root）から GUI を出す場合は、`DISPLAY=:0 XAUTHORITY=/home/ubuntu/.Xauthority` を指定します（`run_demo.sh` では設定済み）。
- 撮影前の画面整理: `python3 scripts/arrange_windows.py`（ターミナルを最小化し、Gazebo を右側に配置）、`python3 scripts/gazebo_view.py 655 335 915 345 3`（Gazebo の左パネルを閉じてズーム。座標は画面に合わせて調整してください）。

---

## 7. よくある問題と対処（開発中に実際に起きたもの）

| 症状 | 原因 | 対処 |
|---|---|---|
| ロボットが AI の指令どおりに動かない | `teleop_keyboard` が `/cmd_vel` を送り続けている | teleop を止め、`ros2 topic hz /cmd_vel` で何も流れていないことを確認する（停止直後は、`ros2 topic info` に古い送信元が `_NODE_NAME_UNKNOWN_` として残ることがあった） |
| 想定と違うロボットが出てくる | `.bashrc` の既定が `happy_mini` | `export TURTLEBOT3_MODEL=burger` してから launch する |
| モニターが "waiting for /ai_nav/probs" のまま | ドライバとモニターを別のユーザーで起動したため、FastDDS の共有メモリ通信が届かない（推定） | 同じユーザーで起動する |
| root で起動した GUI が出ない | X の認証ファイルが見つからない／`/tmp` にある他ユーザーのファイルに書き込めない | `XAUTHORITY` を指定する／ログの保存先を変える |
| 録画に白い円が映る | MATE のスクリーンセーバー（floaters）が作動している | `mate-screensaver-command -d`（ubuntu ユーザーのセッションで実行） |
| `--reset` を付けても開始位置が戻らないことがある | `/reset_world` の呼び出しが失敗している（評価12回中2回）。コードは成否を確認していない | ログの最初の行の x, y が (-2.0, -0.5) になっているか確認する |

---

## 8. 未検証の点
- まっさらな PC で、この手順を最初から通して実行したことはありません。開発は、すでに構築済みだったコンテナの上で行いました。
- Docker Desktop の種類やバージョン、ホストの OS（macOS や Linux など）による違いは確認していません。
- apt 版の TurtleBot3 パッケージや、上記以外のイメージでは試していません。
- noVNC のターミナルから本作品のノードを起動した場合（全ノードが CycloneDDS）の評価はしていません。
