# 启动所有Ablation variant训练的脚本（后台运行）

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Starting Ablation Training" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 激活conda环境
conda activate lc_org_nav

# 创建日志目录
$logDir = "logs_v2/ablation_training"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Write-Host "Training logs will be saved to: $logDir" -ForegroundColor Yellow
Write-Host ""

# 1. w/o ranking loss
Write-Host "Starting training: w/o ranking loss..." -ForegroundColor Cyan
$job1 = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    conda activate lc_org_nav
    python scripts/offline/train_multitask_mixed_v2.py `
        --config configs/gs_experiments/multitask_online_multi_rank_no_rank.yaml `
        2>&1 | Tee-Object -FilePath "logs_v2/ablation_training/no_rank.log"
}
Write-Host "  Job ID: $($job1.Id)" -ForegroundColor Gray
Write-Host "  Log: logs_v2/ablation_training/no_rank.log" -ForegroundColor Gray
Write-Host ""

# 等待第一个任务完成后再启动下一个（避免GPU内存冲突）
Write-Host "Waiting for first variant to complete..." -ForegroundColor Yellow
Write-Host "You can check progress with: Get-Job | Receive-Job" -ForegroundColor Gray
Write-Host ""

# 注意：由于训练需要较长时间，建议手动启动其他variant
Write-Host "To start other variants manually:" -ForegroundColor Yellow
Write-Host "  1. w/o geometry head:" -ForegroundColor White
Write-Host "     python scripts/offline/train_multitask_mixed_v2.py --config configs/gs_experiments/multitask_online_multi_rank_no_geom.yaml" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. single-task GS only:" -ForegroundColor White
Write-Host "     python scripts/offline/train_multitask_mixed_v2.py --config configs/gs_experiments/multitask_online_multi_rank_single_task.yaml" -ForegroundColor Gray
Write-Host ""

Write-Host "To check training status:" -ForegroundColor Yellow
Write-Host "  .\scripts\analysis\check_ablation_training_status.ps1" -ForegroundColor Gray
Write-Host ""

Write-Host "Training started in background!" -ForegroundColor Green

