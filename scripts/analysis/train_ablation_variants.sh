#!/bin/bash
# 训练所有Ablation variant模型的脚本

echo "=========================================="
echo "Training Ablation Variants"
echo "=========================================="

# 设置conda环境
source ~/anaconda3/etc/profile.d/conda.sh
conda activate lc_org_nav

# 1. Full baseline (已有，跳过训练，只记录路径)
echo ""
echo "=========================================="
echo "1. Full baseline (already trained)"
echo "=========================================="
echo "Checkpoint: outputs_v2/multitask_mixed_v2_online_multi_rank/seed_42/best_lc_org_mtl_mixed.pt"
echo ""

# 2. w/o ranking loss
echo ""
echo "=========================================="
echo "2. Training w/o ranking loss"
echo "=========================================="
python scripts/offline/train_multitask_mixed_v2.py \
    --config configs/gs_experiments/multitask_online_multi_rank_no_rank.yaml

if [ $? -eq 0 ]; then
    echo "✅ w/o ranking loss training completed"
else
    echo "❌ w/o ranking loss training failed"
    exit 1
fi

# 3. w/o geometry head
echo ""
echo "=========================================="
echo "3. Training w/o geometry head"
echo "=========================================="
python scripts/offline/train_multitask_mixed_v2.py \
    --config configs/gs_experiments/multitask_online_multi_rank_no_geom.yaml

if [ $? -eq 0 ]; then
    echo "✅ w/o geometry head training completed"
else
    echo "❌ w/o geometry head training failed"
    exit 1
fi

# 4. single-task GS only
echo ""
echo "=========================================="
echo "4. Training single-task GS only"
echo "=========================================="
python scripts/offline/train_multitask_mixed_v2.py \
    --config configs/gs_experiments/multitask_online_multi_rank_single_task.yaml

if [ $? -eq 0 ]; then
    echo "✅ single-task GS training completed"
else
    echo "❌ single-task GS training failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "All ablation variants training completed!"
echo "=========================================="

