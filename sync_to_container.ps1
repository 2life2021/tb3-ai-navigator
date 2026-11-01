# Windows側(正本) -> コンテナ /workspace/tb3_ai_nav へコピー
docker exec pai_ros2 mkdir -p /workspace/tb3_ai_nav
docker cp "$PSScriptRoot/." pai_ros2:/workspace/tb3_ai_nav
