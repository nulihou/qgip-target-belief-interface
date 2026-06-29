# S2S 架构：用于目标选择与跟随的联合学习

## 1. 概述
本文档描述了 LC-ORGNav 的 **Snapshot-to-Sequence (S2S)** 数据采集与学习架构。
该系统旨在生成高质量的成对反事实数据，用于训练能够同时进行 **目标选择 (Target Selection)** 和 **轨迹预测 (Trajectory Prediction)** 的统一 Agent。

> **注意**: 本文档侧重于 *训练流水线*。关于 *推理与控制* 架构（即训练好的模型如何在闭环中使用），请参考 **[CONTROL_SYSTEM_V6.md](./CONTROL_SYSTEM_V6.md)**。关于全系统概览，请参见 **[FULL_SYSTEM_REPORT.md](./FULL_SYSTEM_REPORT.md)**。

## 2. 核心理念：O-E-A 流水线
为了达到 "CVPR 级别" 的数据质量，我们实施了 **Oracle-Expert-Audit (O-E-A)** 流水线：

1.  **Oracle 选择器 (生成阶段)**:
    *   使用严格的几何规则来确定给定指令（例如：“左侧车道前方”）的 Ground Truth 目标。
    *   确保 100% 的标签准确性。如果指令模棱两可或不可行，则丢弃该样本。

2.  **专家控制器 (跟随阶段)**:
    *   使用特权 PID 控制器，该控制器可以访问目标的真实状态。
    *   **重置-回放机制 (Reset-Replay)**: 对于每个场景，我们冻结初始状态 ($t_0$) 并使用不同的目标多次回放该场景（反事实）。
    *   **行为注入**: 随机强制目标刹车或加速，确保数据集覆盖动态交互场景。

3.  **审计器 (质量保证)**:
    *   离线脚本扫描所有生成的样本。
    *   强制执行安全约束（例如：距离 > 2.0m）。
    *   过滤掉不稳定或不完整的轨迹。

## 3. 数据结构 (`JointDataset`)
新的 `.npz` 格式统一了图特征和轨迹数据：

| 字段 | 形状 | 描述 |
| :--- | :--- | :--- |
| `node_feats` | `[N, 32]` | 节点特征 (位置, 速度, 类型) |
| `edge_index` | `[2, E]` | 图连接关系 |
| `lang_feat` | `[32]` | 导航指令的 Embedding |
| `target_index` | `Scalar` | Ground Truth 节点索引 |
| `future_traj` | `[T, 3]` | 专家轨迹 (Ego 相对坐标 X, Y, Yaw) |
| `difficulty` | `String` | Normal / Hard / Ultra (基于诱饵车辆的接近程度) |
| `scene_uuid` | `String` | 用于链接反事实对的唯一 ID |

## 4. 使用指南

### 4.1 数据采集
运行 S2S 采集器以在 `data/s2s_data` 中生成数据：
```bash
python scripts/data/collect_s2s_data.py --town Town03 --num-samples 1000 --num-candidates 6
```
*   `--town`: 地图名称 (Town03, Town05, Town10HD)。
*   `--num-samples`: 基础场景数量。
*   `--num-candidates`: 交通密度 (Ego 周围的候选车辆数)。

### 4.2 质量审计
验证数据集的完整性：
```bash
python scripts/data/audit_s2s_data.py --root data/s2s_data --delete
```
*   `--delete`: 自动删除无效文件。

### 4.3 训练 (下一步)
数据集已准备好用于新的 **Joint LCORGNet**：
*   **Head 1**: 选择头 (Selection Head)，在节点上使用交叉熵损失。
*   **Head 2**: 轨迹头 (Trajectory Head)，在路径点上使用 MSE 损失。
*   **输入**: 共享图骨干网络 (Graph Backbone) + 查询嵌入 (Query Embedding)。

## 5. 论文技术亮点
*   **协议冻结 (Protocol Freezing)**: 消除选择与控制之间的分布偏移。
*   **反事实分支 (Counterfactual Branching)**: 提供“What-If”场景以进行鲁棒推理。
*   **困难负样本挖掘 (Hard Negative Mining)**: “Ultra”难度样本专门针对特定的几何模糊性。
