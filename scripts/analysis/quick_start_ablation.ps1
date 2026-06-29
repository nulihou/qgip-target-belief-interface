# 快速启动Ablation实验的脚本

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Quick Start: Ablation Experiment" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 激活conda环境
Write-Host "Activating conda environment..." -ForegroundColor Yellow
conda activate lc_org_nav

Write-Host ""
Write-Host "选择要执行的操作:" -ForegroundColor Cyan
Write-Host "  1. 训练所有variant（顺序执行，需要较长时间）" -ForegroundColor White
Write-Host "  2. 训练单个variant" -ForegroundColor White
Write-Host "  3. 评估所有variant" -ForegroundColor White
Write-Host "  4. 生成汇总表" -ForegroundColor White
Write-Host "  5. 检查训练状态" -ForegroundColor White
Write-Host "  0. 退出" -ForegroundColor White
Write-Host ""

$choice = Read-Host "请输入选项 (0-5)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "开始训练所有variant..." -ForegroundColor Yellow
        Write-Host "注意: 这需要4-8小时/每个variant" -ForegroundColor Yellow
        Write-Host ""
        
        # w/o ranking loss
        Write-Host "Training w/o ranking loss..." -ForegroundColor Cyan
        python scripts/offline/train_multitask_mixed_v2.py `
            --config configs/gs_experiments/multitask_online_multi_rank_no_rank.yaml
        
        # w/o geometry head
        Write-Host "Training w/o geometry head..." -ForegroundColor Cyan
        python scripts/offline/train_multitask_mixed_v2.py `
            --config configs/gs_experiments/multitask_online_multi_rank_no_geom.yaml
        
        # single-task
        Write-Host "Training single-task GS only..." -ForegroundColor Cyan
        python scripts/offline/train_multitask_mixed_v2.py `
            --config configs/gs_experiments/multitask_online_multi_rank_single_task.yaml
        
        Write-Host ""
        Write-Host "所有训练完成！" -ForegroundColor Green
    }
    "2" {
        Write-Host ""
        Write-Host "选择要训练的variant:" -ForegroundColor Cyan
        Write-Host "  1. w/o ranking loss" -ForegroundColor White
        Write-Host "  2. w/o geometry head" -ForegroundColor White
        Write-Host "  3. single-task GS only" -ForegroundColor White
        Write-Host ""
        
        $variant = Read-Host "请输入选项 (1-3)"
        
        switch ($variant) {
            "1" {
                Write-Host "Training w/o ranking loss..." -ForegroundColor Cyan
                python scripts/offline/train_multitask_mixed_v2.py `
                    --config configs/gs_experiments/multitask_online_multi_rank_no_rank.yaml
            }
            "2" {
                Write-Host "Training w/o geometry head..." -ForegroundColor Cyan
                python scripts/offline/train_multitask_mixed_v2.py `
                    --config configs/gs_experiments/multitask_online_multi_rank_no_geom.yaml
            }
            "3" {
                Write-Host "Training single-task GS only..." -ForegroundColor Cyan
                python scripts/offline/train_multitask_mixed_v2.py `
                    --config configs/gs_experiments/multitask_online_multi_rank_single_task.yaml
            }
        }
    }
    "3" {
        Write-Host ""
        Write-Host "评估所有variant..." -ForegroundColor Cyan
        .\scripts\analysis\run_ablation_evaluation.ps1
    }
    "4" {
        Write-Host ""
        Write-Host "生成汇总表..." -ForegroundColor Cyan
        python scripts/analysis/summarize_ablation_results.py
    }
    "5" {
        Write-Host ""
        .\scripts\analysis\check_ablation_training_status.ps1
    }
    "0" {
        Write-Host "退出" -ForegroundColor Yellow
        exit 0
    }
    default {
        Write-Host "无效选项" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "完成！" -ForegroundColor Green

