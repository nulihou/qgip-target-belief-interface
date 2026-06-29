# 神经-符号控制系统 (V6.3)

## 1. 概述
**神经-符号控制系统 (Neuro-Symbolic Control System)** 是 QGIP-Net 架构的推理时（Inference-time）执行引擎。

**V6.3 更新**: 本版本专注于提升 **系统一致性 (System Consistency)**，通过动态策略调整和软约束机制，弥补了高选择准确率与实际执行成功率之间的落差。

## 2. 架构：Brain-Bridge-Hand 模型

### 2.1 大脑：QGIP-Net (神经部分)
*   **输入**: 场景图 (Scene Graph) + 导航指令 (Navigation Query)。
*   **输出**: 目标选择概率 + 参考轨迹。

### 2.2 桥梁：几何域适应 (增强版)
*   **橡皮筋理论 (Rubber Band Theory)**: 基础的 Sim-to-Real 尺度修正。
*   **V6.3 增益调度 (Gain Scheduling)**:
    *   **问题**: 固定的平滑参数在高速下会导致响应延迟 (Lag)。
    *   **方案**: 引入速度自适应的刚度系数。
    *   $\alpha = \max(0.3, 0.7 - k \cdot v_{ego})$。速度越快，$\alpha$ 越小（越信任当前预测），橡皮筋越“硬”，响应越快。

### 2.3 手：动态避障 MPC (符号部分)
*   **类型**: Lattice-Sampling MPC (V6.3 Soft-Constraint Version)。

## 3. V6.3 控制逻辑细节

### 3.1 动态激进策略 (Dynamic Aggressiveness)
*   **痛点**: 过于保守的安全距离导致目标丢失。
*   **方案**: 利用神经网络的 **预测置信度 (Confidence)**。
    *   如果 `Confidence > 0.8` (非常确信目标)，MPC 将期望车距 (`desired_gap`) 从 15m 缩短至 10m，并允许更小的安全裕度。
    *   这使得系统在“看准了”的时候敢于“跟得紧”。

### 3.2 软约束与碰撞深度 (Soft Constraints)
*   **痛点**: V6.2 的硬约束 ($Cost=\infty$) 导致在极端逼近时 MPC 无解，触发 AEB 刹停，导致任务失败。
*   **方案**: 引入 **碰撞深度 (Collision Depth)** 惩罚。
    *   $J_{collision} = W_{coll} \cdot (1.0 + \text{depth})$
    *   即使所有轨迹都不可避免地有碰撞风险，MPC 也会选择“碰撞最轻微”（即深度最小）的轨迹，而不是直接放弃。这允许车辆在高速下进行极限避让（擦肩而过）。

### 3.3 代价函数设计 (V6.3)
$$
J = J_{soft\_collision} + J_{safety} + J_{efficiency} + J_{comfort} + J_{centering}
$$

1.  **软碰撞 ($J_{soft\_collision}$)**: 权重 $W \approx 10000$。极力避免，但不是绝对禁止。
2.  **动态安全 ($J_{safety}$)**: 安全边界随置信度动态调整。
3.  **效率 ($J_{efficiency}$)**: 包含前馈加速度项，提前响应前车减速。

## 4. 性能目标 (V6.3)
*   **碰撞率**: **< 1.0%** (不再追求极端的 0%，允许为了避险而产生的微小计算误差)。
*   **成功率**: **> 80%** (目标是追平选择准确率)。
*   **能力**:
    *   高速下的紧密跟随。
    *   极限切入场景下的鲁棒性。

---
*文档版本: V6.3 (System Consistency Update)*
