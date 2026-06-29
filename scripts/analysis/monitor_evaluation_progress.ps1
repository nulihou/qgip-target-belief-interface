# 监控评估进度脚本

Write-Host "`n=== 评估进度监控 ===" -ForegroundColor Cyan

$gs_file = "logs_v2/proto_main_eval/gs_proto_driven.jsonl"
$random_file = "logs_v2/proto_main_eval/random_proto_driven.jsonl"

function Count-Lines {
    param($file)
    if (Test-Path $file) {
        return (Get-Content $file | Measure-Object -Line).Lines
    }
    return 0
}

while ($true) {
    $gs_count = Count-Lines $gs_file
    $random_count = Count-Lines $random_file
    
    Write-Host "`n[$(Get-Date -Format 'HH:mm:ss')] GS: $gs_count/30, Random: $random_count/30" -ForegroundColor Yellow
    
    if ($gs_count -ge 30 -and $random_count -ge 30) {
        Write-Host "`n✅ 评估完成！" -ForegroundColor Green
        Write-Host "现在可以运行可视化脚本:" -ForegroundColor Cyan
        Write-Host "  python scripts/analysis/visualize_case_studies.py" -ForegroundColor White
        break
    }
    
    Start-Sleep -Seconds 30
}

