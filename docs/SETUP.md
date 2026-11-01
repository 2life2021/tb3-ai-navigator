# 環境構築 — コンテナの起動から AI 走行まで

## 1. 全体の構成

```
Windows 11（ホスト）
 └─ WSL2（Linux カーネル）
     └─ Docker Desktop 29.8.2（WSL2 バックエンド）
         └─ コンテナ pai_ros2（イメージ airobotbook/ros2-desktop-ai-robot-book-humble）
             ├─ Ubuntu 22.04.5 / ROS 2 Humble / Gazebo 11.10.2 / Python 3.10.12
             ├─ PyTorch 2.6.0・numpy・OpenCV・matplotlib（イメージに同梱）
             ├─ VNC デスクトップ → ブラウザから noVNC で表示（http://localhost:6080）
             ├─ ~/airobot_ws : TurtleBot3 のシミュレーションパッケージ（ソースからビルド済み）
             └─ /workspace   : ホストのディレクトリをマウント（本リポジトリを置く場所）
```

GPU は使いません。本作品のために追加でインストールしたものはなく、必要なものはすべてイメージに入っています。

| 層 | 役割 | 本作品の環境 |
|---|---|---|
| WSL2 | Windows 上で Linux カーネルを動かす | Windows 11 の WSL2 |
| Docker | アプリと実行環境をまとめた「コンテナ」を動かす。コンテナは自分のカーネルを持たず、ホスト側（WSL2）の Linux カーネルを共有する | Docker Desktop 29.8.2 |
| Docker イメージ | OS・ROS 2・Gazebo・ライブラリ・デスクトップ環境が入ったコンテナのひな形 | `airobotbook/ros2-desktop-ai-robot-book-humble` |
| ROS 2 Humble | ノード間の通信を担うミドルウェア | apt で導入済み（`/opt/ros/humble`） |
| DDS（RMW） | ROS 2 の通信を実際に運ぶ層 | FastDDS と CycloneDDS |
| Gazebo 11 | ロボットとセンサの物理シミュレータ。`gazebo_ros` で ROS 2 とつながる | Gazebo 11.10.2、`ros-humble-gazebo-ros-pkgs` |
| TurtleBot3 | ロボットのモデル・ワールド・launch ファイル | `~/airobot_ws` の `turtlebot3_gazebo` 2.2.6（AI-Robot-Book-Humble/turtlebot3_happy_mini） |

### ROS 2 の有効化のしくみ
ROS 2 のコマンドやパッケージは、`setup.bash` を `source` すると使えるようになります。このコンテナでは、`~/.bashrc` が次の順に読み込みます。

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp   # DDS 実装の指定
source /usr/share/gazebo/setup.sh              # Gazebo の環境変数
export TURTLEBOT3_MODEL=happy_mini             # ← 本作品では burger に上書きして使う
source /opt/ros/humble/setup.bash              # 下地（underlay）: apt で入れた ROS 2 本体
source ~/airobot_ws/install/setup.bash         # 上乗せ（overlay）: ソースからビルドしたパッケージ
```

`/opt/ros/humble` を土台に、`colcon build` でビルドしたワークスペース `~/airobot_ws` を重ねています。同じ名前のパッケージがあると、上に重ねた方が優先されます。

---

## 2. コンテナの起動

Docker Desktop（WSL2 バックエンド）を用意し、マウントしたいディレクトリで次を実行します。イメージは約 25 GB です。

```bash
docker run -d --name pai_ros2 \
  -p 6080:80 --shm-size=512m \
  -v "$(pwd)":/workspace \
  airobotbook/ros2-desktop-ai-robot-book-humble:latest
```

- `-p 6080:80`: ブラウザで http://localhost:6080 を開くと、コンテナのデスクトップが表示されます。
- `--shm-size=512m`: 共有メモリのサイズです（Gazebo や DDS が使います）。
- `-v "$(pwd)":/workspace`: 実行したディレクトリが、コンテナの `/workspace` になります。
- 開発時のイメージ: `airobotbook/ros2-desktop-ai-robot-book-humble@sha256:b58ec74c019aacd9ce4818fa25fc5a9e0a1f22f8c9cd1f5260994bf15cd9eb63`

2回目以降は `docker start pai_ros2` で起動します。

---

## 3. コードの配置

```bash
cd /workspace
git clone https://github.com/2life2021/tb3-ai-navigator.git
cd tb3-ai-navigator
```

---

## 4. シミュレーションの起動

noVNC のデスクトップでターミナルを開き、次を実行します。

```bash
export TURTLEBOT3_MODEL=burger      # 必須（.bashrc の既定は happy_mini）
ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py
```

ロボットは (-2.0, -0.5) に出現します。別のターミナルで起動を確認します。

```bash
ros2 topic list | grep -E "^/(scan|cmd_vel|odom)$"   # 3つとも表示されること
ros2 topic hz /scan                                   # 約 5Hz
ros2 topic hz /cmd_vel                                # AI を起動する前は、何も流れていないこと
```

---

## 5. AI 走行の実行

```bash
cd /workspace/tb3-ai-navigator
python3 scripts/ai_driver.py --model models/policy_v2_aug.pt --reset
# Ctrl+C で停止。--duration 120 で120秒後に自動停止。--control soft で soft 制御
```

- **`teleop_keyboard` は止めておいてください**。キーを押していなくても `/cmd_vel` にゼロ速度を送り続け、AI の指令と競合します。
- 開発時は、ホストから `docker exec pai_ros2 bash -lc "source /opt/ros/humble/setup.bash; ..."` で本作品のノードを起動しました（この場合 RMW は既定の FastDDS）。本作品のノードは ROS 2 の標準メッセージだけを使うので、`/opt/ros/humble` を読み込めば動きます。

### AI 視点モニターとデモ撮影（任意）
```bash
python3 scripts/ai_monitor.py                 # ai_driver と同じユーザーで起動すること
bash scripts/run_demo.sh 150                  # モニター + 走行 + 録画 → video/demo.mp4
```
撮影前の画面整理には `scripts/arrange_windows.py`（ターミナルを最小化し、Gazebo を右側に配置）と `scripts/gazebo_view.py`（Gazebo の表示を調整）を使いました。

---

## 6. よくある問題と対処

| 症状 | 原因 | 対処 |
|---|---|---|
| ロボットが AI の指令どおりに動かない | `teleop_keyboard` が `/cmd_vel` を送り続けている | teleop を止め、`ros2 topic hz /cmd_vel` で何も流れていないことを確認する |
| 想定と違うロボットが出てくる | `.bashrc` の既定が `happy_mini` | `export TURTLEBOT3_MODEL=burger` してから launch する |
| モニターが "waiting for /ai_nav/probs" のまま | ドライバとモニターを別のユーザーで起動している | 同じユーザーで起動する |
| `--reset` を付けても開始位置が戻らないことがある | `/reset_world` の呼び出しが失敗している | 走行ログの最初の行の x, y が (-2.0, -0.5) になっているか確認する |
