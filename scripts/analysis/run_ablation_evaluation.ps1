# PowerShell脚本：评估所有Ablation variant

$PROTOCOL_DIR = "scripts/online_multi/protocol_graphs"
$OUTPUT_DIR = "logs_v2/proto_main_eval/ablation"

# 创建输出目录
New-Item -ItemType Directory -Force -Path $OUTPUT_DIR | Out-Null

# Full (baseline)
Write-Host "Evaluating Full (baseline)..." -ForegroundColor Cyan
python scripts/online_multi/proto_eval/eval_gs_protocol.py `
    --checkpoint outputs_v2/multitask_mixed_v2_online_multi_rank/seed_42/best_lc_org_mtl_mixed.pt `
    --protocol-dir $PROTOCOL_DIR `
    --output "$OUTPUT_DIR/full.jsonl" `
    --max-scen-id 29

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Full evaluation failed" -ForegroundColor Red
    exit 1
}

# w/o ranking
Write-Host "Evaluating w/o ranking loss..." -ForegroundColor Cyan
python scripts/online_multi/proto_eval/eval_gs_protocol.py `
    --checkpoint outputs_v2/ablation_no_rank/best_lc_org_mtl_mixed_v2_no_rank.pt `
    --protocol-dir $PROTOCOL_DIR `
    --output "$OUTPUT_DIR/no_rank.jsonl" `
    --max-scen-id 29

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ w/o ranking evaluation failed" -ForegroundColor Red
    exit 1
}

# w/o geometry
Write-Host "Evaluating w/o geometry head..." -ForegroundColor Cyan
python scripts/online_multi/proto_eval/eval_gs_protocol.py `
    --checkpoint outputs_v2/ablation_no_geom/best_lc_org_mtl_mixed_v2_no_geom.pt `
    --protocol-dir $PROTOCOL_DIR `
    --output "$OUTPUT_DIR/no_geom.jsonl" `
    --max-scen-id 29

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ w/o geometry evaluation failed" -ForegroundColor Red
    exit 1
}

# single-task
Write-Host "Evaluating single-task GS only..." -ForegroundColor Cyan
python scripts/online_multi/proto_eval/eval_gs_protocol.py `
    --checkpoint outputs_v2/ablation_single_task/best_lc_org_mtl_mixed_v2_single_task.pt `
    --protocol-dir $PROTOCOL_DIR `
    --output "$OUTPUT_DIR/single_task.jsonl" `
    --max-scen-id 29

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ single-task evaluation failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "All ablation evaluations completed!" -ForegroundColor Green

