# 监控轨迹评估进度
# 检查三个评估任务的进度

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "轨迹评估进度监控" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$gs_file = "logs_v2/proto_main_eval/trajectory_eval/gs_proto_driven.jsonl"
$random_file = "logs_v2/proto_main_eval/trajectory_eval/random_proto_driven.jsonl"
$oracle_file = "logs_v2/proto_main_eval/trajectory_eval/oracle_proto_driven.jsonl"

function Count-Lines {
    param($file)
    if (Test-Path $file) {
        $lines = Get-Content $file | Where-Object { $_.Trim() -ne "" }
        return $lines.Count
    }
    return 0
}

$gs_count = Count-Lines $gs_file
$random_count = Count-Lines $random_file
$oracle_count = Count-Lines $oracle_file

Write-Host "GS模式:      $gs_count / 30 episodes" -ForegroundColor $(if ($gs_count -eq 30) { "Green" } else { "Yellow" })
Write-Host "Random模式:  $random_count / 30 episodes" -ForegroundColor $(if ($random_count -eq 30) { "Green" } else { "Yellow" })
Write-Host "Oracle模式:  $oracle_count / 30 episodes" -ForegroundColor $(if ($oracle_count -eq 30) { "Green" } else { "Yellow" })
Write-Host ""

if ($gs_count -eq 30 -and $random_count -eq 30 -and $oracle_count -eq 30) {
    Write-Host "✅ 所有评估已完成！" -ForegroundColor Green
} else {
    Write-Host "⏳ 评估进行中..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "提示: 可以重复运行此脚本查看最新进度" -ForegroundColor Gray
}

