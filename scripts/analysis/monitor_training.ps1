# 监控Ablation训练进度的脚本

param(
    [string]$Variant = "all"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Ablation Training Monitor" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$variants = @(
    @{Name = "w/o ranking loss"; Log = "logs_v2/ablation_training/no_rank.log"; Checkpoint = "outputs_v2/ablation_no_rank/best_lc_org_mtl_mixed_v2_no_rank.pt"},
    @{Name = "w/o geometry head"; Log = "logs_v2/ablation_training/no_geom.log"; Checkpoint = "outputs_v2/ablation_no_geom/best_lc_org_mtl_mixed_v2_no_geom.pt"},
    @{Name = "single-task GS only"; Log = "logs_v2/ablation_training/single_task.log"; Checkpoint = "outputs_v2/ablation_single_task/best_lc_org_mtl_mixed_v2_single_task.pt"}
)

foreach ($v in $variants) {
    if ($Variant -ne "all" -and $v.Name -notlike "*$Variant*") {
        continue
    }
    
    Write-Host "----------------------------------------" -ForegroundColor Yellow
    Write-Host "$($v.Name)" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Yellow
    
    # 检查checkpoint
    if (Test-Path $v.Checkpoint) {
        $ckpt = Get-Item $v.Checkpoint
        $sizeMB = [math]::Round($ckpt.Length / 1MB, 2)
        Write-Host "✅ Checkpoint exists: $sizeMB MB" -ForegroundColor Green
        Write-Host "   Modified: $($ckpt.LastWriteTime)" -ForegroundColor Gray
        Write-Host "   Status: Training completed!" -ForegroundColor Green
    } else {
        Write-Host "⏳ Checkpoint not found: Training in progress or not started" -ForegroundColor Yellow
    }
    
    # 检查日志
    if (Test-Path $v.Log) {
        $log = Get-Item $v.Log
        $sizeKB = [math]::Round($log.Length / 1KB, 2)
        Write-Host "📝 Log file: $sizeKB KB" -ForegroundColor Cyan
        Write-Host "   Modified: $($log.LastWriteTime)" -ForegroundColor Gray
        
        # 显示最后几行
        Write-Host ""
        Write-Host "Last 10 lines:" -ForegroundColor Gray
        Get-Content $v.Log -Tail 10 | ForEach-Object {
            Write-Host "  $_" -ForegroundColor DarkGray
        }
    } else {
        Write-Host "📝 Log file not found: Training may not have started yet" -ForegroundColor Yellow
    }
    
    Write-Host ""
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Quick Commands:" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "View live log (w/o ranking):" -ForegroundColor White
Write-Host "  Get-Content logs_v2/ablation_training/no_rank.log -Wait -Tail 20" -ForegroundColor Gray
Write-Host ""
Write-Host "Check training status:" -ForegroundColor White
Write-Host "  .\scripts\analysis\check_ablation_training_status.ps1" -ForegroundColor Gray
Write-Host ""

