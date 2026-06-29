# PowerShell脚本：检查Ablation训练状态

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Ablation Training Status Check" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 检查checkpoint文件是否存在
$variants = @(
    @{
        Name = "Full (baseline)";
        Path = "outputs_v2/multitask_mixed_v2_online_multi_rank/seed_42/best_lc_org_mtl_mixed.pt";
        Required = $true
    },
    @{
        Name = "w/o ranking loss";
        Path = "outputs_v2/ablation_no_rank/best_lc_org_mtl_mixed_v2_no_rank.pt";
        Required = $false
    },
    @{
        Name = "w/o geometry head";
        Path = "outputs_v2/ablation_no_geom/best_lc_org_mtl_mixed_v2_no_geom.pt";
        Required = $false
    },
    @{
        Name = "single-task GS only";
        Path = "outputs_v2/ablation_single_task/best_lc_org_mtl_mixed_v2_single_task.pt";
        Required = $false
    }
)

$allReady = $true

foreach ($variant in $variants) {
    $exists = Test-Path $variant.Path
    
    if ($exists) {
        $fileInfo = Get-Item $variant.Path
        $sizeMB = [math]::Round($fileInfo.Length / 1MB, 2)
        Write-Host "✅ $($variant.Name): " -NoNewline -ForegroundColor Green
        Write-Host "$($variant.Path)" -ForegroundColor White
        Write-Host "   Size: $sizeMB MB, Modified: $($fileInfo.LastWriteTime)" -ForegroundColor Gray
    } else {
        if ($variant.Required) {
            Write-Host "❌ $($variant.Name): " -NoNewline -ForegroundColor Red
            Write-Host "MISSING (Required)" -ForegroundColor Red
            $allReady = $false
        } else {
            Write-Host "⏳ $($variant.Name): " -NoNewline -ForegroundColor Yellow
            Write-Host "Not trained yet" -ForegroundColor Yellow
            $allReady = $false
        }
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Evaluation Status" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$evalFiles = @(
    @{Name = "Full"; Path = "logs_v2/proto_main_eval/ablation/full.jsonl"},
    @{Name = "w/o ranking"; Path = "logs_v2/proto_main_eval/ablation/no_rank.jsonl"},
    @{Name = "w/o geometry"; Path = "logs_v2/proto_main_eval/ablation/no_geom.jsonl"},
    @{Name = "single-task"; Path = "logs_v2/proto_main_eval/ablation/single_task.jsonl"}
)

foreach ($eval in $evalFiles) {
    $exists = Test-Path $eval.Path
    
    if ($exists) {
        $lineCount = (Get-Content $eval.Path | Measure-Object -Line).Lines
        Write-Host "✅ $($eval.Name): " -NoNewline -ForegroundColor Green
        Write-Host "$lineCount scenarios evaluated" -ForegroundColor White
    } else {
        Write-Host "⏳ $($eval.Name): " -NoNewline -ForegroundColor Yellow
        Write-Host "Not evaluated yet" -ForegroundColor Yellow
    }
}

Write-Host ""

if ($allReady) {
    Write-Host "✅ All variants are ready for evaluation!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next step: Run evaluation script" -ForegroundColor Cyan
    Write-Host "  .\scripts\analysis\run_ablation_evaluation.ps1" -ForegroundColor White
} else {
    Write-Host "⏳ Some variants are still training or missing" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Wait for training to complete" -ForegroundColor White
    Write-Host "  2. Check training logs for errors" -ForegroundColor White
    Write-Host "  3. Run this script again to check status" -ForegroundColor White
}

