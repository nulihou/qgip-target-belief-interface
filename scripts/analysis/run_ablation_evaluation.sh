#!/bin/bash
# 评估所有Ablation variant的脚本

PROTOCOL_DIR="scripts/online_multi/protocol_graphs"
OUTPUT_DIR="logs_v2/proto_main_eval/ablation"

# 创建输出目录
mkdir -p ${OUTPUT_DIR}

# Full (baseline)
echo "Evaluating Full (baseline)..."
python scripts/online_multi/proto_eval/eval_gs_protocol.py \
    --checkpoint outputs_v2/multitask_mixed_v2_online_multi_rank/seed_42/best_lc_org_mtl_mixed.pt \
    --protocol-dir ${PROTOCOL_DIR} \
    --output ${OUTPUT_DIR}/full.jsonl \
    --max-scen-id 29

# w/o ranking
echo "Evaluating w/o ranking loss..."
python scripts/online_multi/proto_eval/eval_gs_protocol.py \
    --checkpoint outputs_v2/ablation_no_rank/best_lc_org_mtl_mixed_v2_no_rank.pt \
    --protocol-dir ${PROTOCOL_DIR} \
    --output ${OUTPUT_DIR}/no_rank.jsonl \
    --max-scen-id 29

# w/o geometry
echo "Evaluating w/o geometry head..."
python scripts/online_multi/proto_eval/eval_gs_protocol.py \
    --checkpoint outputs_v2/ablation_no_geom/best_lc_org_mtl_mixed_v2_no_geom.pt \
    --protocol-dir ${PROTOCOL_DIR} \
    --output ${OUTPUT_DIR}/no_geom.jsonl \
    --max-scen-id 29

# single-task
echo "Evaluating single-task GS only..."
python scripts/online_multi/proto_eval/eval_gs_protocol.py \
    --checkpoint outputs_v2/ablation_single_task/best_lc_org_mtl_mixed_v2_single_task.pt \
    --protocol-dir ${PROTOCOL_DIR} \
    --output ${OUTPUT_DIR}/single_task.jsonl \
    --max-scen-id 29

echo "All ablation evaluations completed!"

