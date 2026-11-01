# コンテナで生成したデータ・モデル・ログを Windows側へ回収
foreach ($d in "data", "models", "logs") {
    docker cp "pai_ros2:/workspace/tb3_ai_nav/$d/." "$PSScriptRoot/$d"
}
