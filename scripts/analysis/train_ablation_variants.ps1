# PowerShell脚本：训练所有Ablation variant模型

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Training Ablation Variants" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 激活conda环境
conda activate lc_org_nav

# 1. Full baseline (已有，跳过训练，只记录路径)
Write-Host ""
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "1. Full baseline (already trained)" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "Checkpoint: outputs_v2/multitask_mixed_v2_online_multi_rank/seed_42/best_lc_org_mtl_mixed.pt"
Write-Host ""

# 2. w/o ranking loss
Write-Host ""
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "2. Training w/o ranking loss" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
python scripts/offline/train_multitask_mixed_v2.py `
    --config configs/gs_experiments/multitask_online_multi_rank_no_rank.yaml

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ w/o ranking loss training completed" -ForegroundColor Green
} else {
    Write-Host "❌ w/o ranking loss training failed" -ForegroundColor Red
    exit 1
}

# 3. w/o geometry head
Write-Host ""
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "3. Training w/o geometry head" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
python scripts/offline/train_multitask_mixed_v2.py `
    --config configs/gs_experiments/multitask_online_multi_rank_no_geom.yaml

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ w/o geometry head training completed" -ForegroundColor Green
} else {
    Write-Host "❌ w/o geometry head training failed" -ForegroundColor Red
    exit 1
}

# 4. single-task GS only
Write-Host ""
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "4. Training single-task GS only" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
python scripts/offline/train_multitask_mixed_v2.py `
    --config configs/gs_experiments/multitask_online_multi_rank_single_task.yaml

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ single-task GS training completed" -ForegroundColor Green
} else {
    Write-Host "❌ single-task GS training failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "All ablation variants training completed!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

