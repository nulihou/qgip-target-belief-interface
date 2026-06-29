# QGIP-Net 系统架构设计说明书 (用于绘图)

> **目的**：本文档旨在为您绘制系统架构图提供精确的结构定义和数据流描述。请依据此文档中的模块划分和连接关系进行绘图。

---

## 1. 顶层架构概览 (Top-Level Overview)

整个系统采用 **"感知-决策-控制" (Perception-Decision-Control)** 的分层流水线架构，并辅以 **"神经-符号" (Neuro-Symbolic)** 混合设计。

*   **输入**: 环境观测状态 (Observed Environment State) + 用户指令 (Query)。
*   **核心**: 图神经网络 (GNN) + 卡尔曼滤波 (KF) + 模型预测控制 (MPC)。
*   **输出**: 车辆控制信号 (Control Commands)。

---

## 2. 详细模块拆解 (Detailed Modules)

请在图中画出以下四个主要方框（子系统）：

### A. 环境感知模块 (Environment Perception)
负责将环境观测数据转化为结构化的图数据。
*   **输入**:
    *   `Ego State`: 自车位置、速度、航向角。
    *   `Surrounding Actors`: 周围车辆列表 (List of Vehicles)。
*   **处理单元**:
    *   **Scene Graph Builder**:
        *   构建节点 (Nodes): 每辆车一个节点。
        *   构建特征 (Features): 计算相对距离、角度、速度 (极坐标系)。
        *   构建边 (Edges): 全连接图，计算车辆间的空间关系。
*   **输出**: `Graph Data (x, edge_index, edge_attr)`。

### B. 意图决策模块 (Intent Decision - V7.0/V7.2)
系统的“大脑”，负责选择目标并维持追踪。
*   **输入**: `Graph Data` + `Query Vector`。
*   **处理单元**:
    *   **GNN Encoder (GATv2)**: 提取高维特征，输出每辆车的“被关注概率” (Attention Scores)。
    *   **Leader Classifier (LLC)**: 这是一个 MLP 头，输出最终的 `Target ID` (Softmax)。
    *   **Kalman Filter (KF)**:
        *   **Update**: 如果 GNN 选中了目标，用观测值更新 KF 状态。
        *   **Predict (Ghost Tracking)**: 如果 GNN 丢失目标 (Lost)，KF 负责“脑补”目标位置。
*   **输出**: `Target State (x, y, vx, vy)` (这是经过 KF 平滑或预测后的最优估计)。

### C. 运动规划模块 (Motion Planning)
负责生成一条平滑的轨迹让车去追。
*   **输入**: `Target State` + `Map Data` (可选)。
*   **处理单元**:
    *   **Trajectory Generator**: 生成从 Ego 到 Target 的一系列路点 (Waypoints)。
    *   **Rubber Band Smoothing**: 像橡皮筋一样，根据距离动态拉伸轨迹点，防止急刹急停。
*   **输出**: `Reference Trajectory (List of Waypoints)`。

### D. 鲁棒控制模块 (Robust Control - V6.4)
系统的“小脑”，负责把轨迹转化为油门刹车，并保证绝对安全。
*   **输入**: `Reference Trajectory` + `Target State` + `Ego State`。
*   **处理单元**:
    *   **Lateral PID**: 仅仅负责把方向盘打准，让车压在轨迹线上。
    *   **Lattice-Sampling MPC (Logic + Hard Constraint)**:
        *   采样多种加速度 (Accel Candidates) 与离散横向偏移 (Lane Offset Candidates)。
        *   **碰撞检测 (Safety Shield)**: 如果某条候选在短时域内会碰撞，直接剔除（Cost = Infinity）。
        *   成本函数 (Cost Function): 综合考虑跟车距离、舒适度、变道惩罚与效率（如超车奖励）。
*   **输出**: `Control (Throttle, Steer, Brake)`。

---

## 3. 数据流向图 (Data Flow Connections)

请在绘图时用箭头连接以下节点：

1.  **[CARLA World]** --> `Actor List` --> **[Scene Graph Builder]**
2.  **[Scene Graph Builder]** --> `Graph (Nodes/Edges)` --> **[GNN Encoder]**
3.  **[GNN Encoder]** --> `Features` --> **[Leader Classifier]**
4.  **[Leader Classifier]** --> `Target ID` --> **[Kalman Filter]**
    *   *(标注: If Target Found -> Update)*
    *   *(标注: If Target Lost -> Predict)*
5.  **[Kalman Filter]** --> `Target State (Smoothed)` --> **[Trajectory Generator]**
6.  **[Trajectory Generator]** --> `Reference Trajectory` --> **[Lateral PID]** & **[Lattice-Sampling MPC]**
7.  **[MPC]** --> `Throttle/Brake (+ Lane Offset)` --> **[Vehicle Actuator]**
8.  **[PID]** --> `Steer` --> **[Vehicle Actuator]**

---

## 4. 关键图注 (Key Legends)

*   **蓝色模块**: 神经网络 (Learnable)。代表 V7.0 的核心创新。
*   **绿色模块**: 数学模型 (Mathematical)。代表 V7.2 的 KF 和 V6.4 的 MPC。
*   **红色连线**: 幽灵追踪路径 (Ghost Tracking Path)。代表系统在盲区时的备用数据流。

---
*By QGIP-Net Project Team*
