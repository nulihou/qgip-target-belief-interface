# L2 Ablation实验完整指南

**创建日期**: 2025-11-23  
**状态**: 训练脚本已准备，Full baseline已评估

---

## 📋 实验概览

本实验对比4个variant：
1. **Full (baseline)**: λ_rel=0.1, λ_geom=0.02, λ_rank=0.1 ✅ 已训练
2. **w/o ranking loss**: λ_rank=0.0 ⏳ 训练中
3. **w/o geometry head**: λ_geom=0.0 ⏳ 待训练
4. **single-task GS only**: λ_rel=0.0, λ_geom=0.0 ⏳ 待训练

---

## 🚀 执行步骤

### Step 1: 训练3个variant模型

#### 方式1: 使用PowerShell脚本（Windows推荐）

```powershell
conda activate lc_org_nav
.\scripts\analysis\train_ablation_variants.ps1
```

#### 方式2: 手动训练（逐个执行）

```powershell
# 1. w/o ranking loss
conda activate lc_org_nav
python scripts/offline/train_multitask_mixed_v2.py `
    --config configs/gs_experiments/multitask_online_multi_rank_no_rank.yaml

# 2. w/o geometry head
python scripts/offline/train_multitask_mixed_v2.py `
    --config configs/gs_experiments/multitask_online_multi_rank_no_geom.yaml

# 3. single-task GS only
python scripts/offline/train_multitask_mixed_v2.py `
    --config configs/gs_experiments/multitask_online_multi_rank_single_task.yaml
```

**注意**: 
- 每个variant训练需要约4-8小时（取决于GPU）
- 可以并行训练（如果有多个GPU）
- 建议使用更少的epoch（如40-50）来节省时间，只要收敛趋势稳定即可

**修改epoch数**:
```powershell
python scripts/offline/train_multitask_mixed_v2.py `
    --config configs/gs_experiments/multitask_online_multi_rank_no_rank.yaml `
    --epochs 40
```

---

### Step 2: 评估所有variant

#### 方式1: 使用PowerShell脚本

```powershell
conda activate lc_org_nav
.\scripts\analysis\run_ablation_evaluation.ps1
```

#### 方式2: 手动评估

```powershell
# 创建输出目录
New-Item -ItemType Directory -Force -Path logs_v2/proto_main_eval/ablation

# 1. Full baseline (已完成)
python scripts/online_multi/proto_eval/eval_gs_protocol.py `
    --checkpoint outputs_v2/multitask_mixed_v2_online_multi_rank/seed_42/best_lc_org_mtl_mixed.pt `
    --protocol-dir scripts/online_multi/protocol_graphs `
    --output logs_v2/proto_main_eval/ablation/full.jsonl `
    --max-scen-id 29

# 2. w/o ranking loss
python scripts/online_multi/proto_eval/eval_gs_protocol.py `
    --checkpoint outputs_v2/ablation_no_rank/best_lc_org_mtl_mixed_v2_no_rank.pt `
    --protocol-dir scripts/online_multi/protocol_graphs `
    --output logs_v2/proto_main_eval/ablation/no_rank.jsonl `
    --max-scen-id 29

# 3. w/o geometry head
python scripts/online_multi/proto_eval/eval_gs_protocol.py `
    --checkpoint outputs_v2/ablation_no_geom/best_lc_org_mtl_mixed_v2_no_geom.pt `
    --protocol-dir scripts/online_multi/protocol_graphs `
    --output logs_v2/proto_main_eval/ablation/no_geom.jsonl `
    --max-scen-id 29

# 4. single-task GS only
python scripts/online_multi/proto_eval/eval_gs_protocol.py `
    --checkpoint outputs_v2/ablation_single_task/best_lc_org_mtl_mixed_v2_single_task.pt `
    --protocol-dir scripts/online_multi/protocol_graphs `
    --output logs_v2/proto_main_eval/ablation/single_task.jsonl `
    --max-scen-id 29
```

**注意**: 
- 每个variant评估需要约2-3分钟
- 确保checkpoint文件存在后再评估

---

### Step 3: 生成Ablation对比表

```powershell
conda activate lc_org_nav
python scripts/analysis/summarize_ablation_results.py
```

**输出文件**:
- `results/proto_main_eval/ablation_summary.md` - 完整的ablation对比表

---

## 📊 预期结果格式

### Ablation对比表

```
| Variant | GS@1 (proto) |
|---------|--------------|
| Full (baseline) | 93.3% |
| w/o ranking loss | XX.X% |
| w/o geometry head | XX.X% |
| single-task GS | XX.X% |
```

### 关键发现

- Full model achieves 93.3% GS@1 on protocol graphs
- Removing ranking loss decreases performance by X.X percentage points
- Removing geometry head decreases performance by X.X percentage points
- Single-task model decreases performance by X.X percentage points

---

## 📁 文件位置

### 配置文件
- `configs/gs_experiments/multitask_online_multi_rank.yaml` (Full baseline)
- `configs/gs_experiments/multitask_online_multi_rank_no_rank.yaml`
- `configs/gs_experiments/multitask_online_multi_rank_no_geom.yaml`
- `configs/gs_experiments/multitask_online_multi_rank_single_task.yaml`

### Checkpoint位置
- Full: `outputs_v2/multitask_mixed_v2_online_multi_rank/seed_42/best_lc_org_mtl_mixed.pt`
- w/o ranking: `outputs_v2/ablation_no_rank/best_lc_org_mtl_mixed_v2_no_rank.pt`
- w/o geometry: `outputs_v2/ablation_no_geom/best_lc_org_mtl_mixed_v2_no_geom.pt`
- single-task: `outputs_v2/ablation_single_task/best_lc_org_mtl_mixed_v2_single_task.pt`

### 评估结果
- `logs_v2/proto_main_eval/ablation/full.jsonl`
- `logs_v2/proto_main_eval/ablation/no_rank.jsonl`
- `logs_v2/proto_main_eval/ablation/no_geom.jsonl`
- `logs_v2/proto_main_eval/ablation/single_task.jsonl`

### 汇总报告
- `results/proto_main_eval/ablation_summary.md`

---

## ⚠️ 注意事项

1. **训练时间**: 每个variant需要4-8小时，建议在GPU上运行
2. **Checkpoint检查**: 训练完成后，检查checkpoint文件是否存在
3. **评估顺序**: 可以等所有variant训练完成后再统一评估
4. **并行训练**: 如果有多个GPU，可以同时训练多个variant

---

## ✅ 当前状态

- ✅ Full baseline已训练并评估
- ⏳ w/o ranking loss训练中（后台运行）
- ⏳ w/o geometry head待训练
- ⏳ single-task GS only待训练

---

**最后更新**: 2025-11-23  
**下一步**: 等待训练完成，然后运行评估脚本

