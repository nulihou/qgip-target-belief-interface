#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GS 2×2 行为轨迹图
展示四种"目标选择 × 导航结果"组合下的典型轨迹
"""

import json
import matplotlib.pyplot as plt
from pathlib import Path

# === 路径设置：轨迹 jsonl 所在目录 ===
BASE_DIR = Path("visualization_data/trajectory_eval")

def load_episode(mode, scen_id):
    """
    mode: 'gs', 'random', or 'oracle'
    scen_id: integer scene id
    从对应 jsonl 中找到指定场景的完整 episode（含 trajectory）
    """
    fname_map = {
        "gs": "gs_proto_driven.jsonl",
        "random": "random_proto_driven.jsonl",
        "oracle": "oracle_proto_driven.jsonl",
    }
    path = BASE_DIR / fname_map[mode]
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            ep = json.loads(line)
            if ep.get("scen_id") == scen_id or ep.get("episode") == scen_id:
                return ep
    raise ValueError(f"episode with scen_id={scen_id} not found in mode={mode}")

def extract_xy(ep, center_to_goal=True):
    """
    从 episode 提取 2D 坐标。
    若 center_to_goal=True，则把目标平移到原点。
    返回: xs, ys, gx, gy
    """
    traj = ep.get("trajectory", [])
    if not traj:
        return [], [], 0.0, 0.0
    
    xs = [p.get("x", 0.0) for p in traj]
    ys = [p.get("y", 0.0) for p in traj]
    
    # 获取目标位置
    target_pos = ep.get("target_position", {})
    if not target_pos:
        # 如果没有target_position，尝试从其他字段获取
        gx = ep.get("target_start_position", {}).get("x", 0.0)
        gy = ep.get("target_start_position", {}).get("y", 0.0)
    else:
        gx = target_pos.get("x", 0.0)
        gy = target_pos.get("y", 0.0)
    
    if center_to_goal:
        xs = [x - gx for x in xs]
        ys = [y - gy for y in ys]
        gx, gy = 0.0, 0.0
    
    return xs, ys, gx, gy

def plot_single_traj(ax, ep, title, show_radius=True, radius=8.0):
    """
    在给定 ax 上画一个 episode 的轨迹图（俯视）。
    - 轨迹线
    - 起点 / 终点 / 目标
    - （可选）8m 成功半径圆
    """
    xs, ys, gx, gy = extract_xy(ep, center_to_goal=True)
    
    if not xs or not ys:
        ax.text(0.5, 0.5, "No trajectory data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(title, fontsize=9)
        return
    
    # main trajectory line
    ax.plot(xs, ys, linewidth=1.5, color='#2E86AB', alpha=0.8)
    
    # start / end / goal
    ax.scatter(xs[0], ys[0], marker="o", s=20, color='#28A745', label="Start", zorder=5)
    ax.scatter(xs[-1], ys[-1], marker="s", s=24, color='#E63946', label="End", zorder=5)
    ax.scatter(gx, gy, marker="*", s=40, color='#FFC107', label="Goal", zorder=5)
    
    # success radius (8m)
    if show_radius:
        circle = plt.Circle((gx, gy), radius, fill=False,
                            linestyle="--", linewidth=1.0, color='gray', alpha=0.5)
        ax.add_patch(circle)
    
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, fontsize=9)

# === 1) GS 2×2 行为图 ===
# 四个代表性 scen_id（来自 gs_proto_driven.jsonl）：
# 8  : 选对 + 成功
# 0  : 选对 + 失败
# 6  : 选错 + 成功
# 24 : 选错 + 失败

cases = [
    # (row, col, scen_id, text label)
    (0, 0, 8,  "Correct selection, success@8m"),
    (0, 1, 0,  "Correct selection, fail@8m"),
    (1, 0, 6,  "Wrong selection, success@8m"),
    (1, 1, 24, "Wrong selection, fail@8m"),
]

fig, axes = plt.subplots(2, 2, figsize=(6, 6), dpi=300)

for row, col, scen_id, label in cases:
    try:
        ep = load_episode("gs", scen_id)
        # 用真实数据做 subtitle
        steps = ep.get('steps', 0)
        start_dist = ep.get('start_dist', 0.0)
        final_dist = ep.get('final_dist', 0.0)
        
        subtitle = (
            f"scen {scen_id} | steps={steps} | "
            f"start={start_dist:.1f}m, final={final_dist:.1f}m"
        )
        full_title = f"{label}\n{subtitle}"
        ax = axes[row][col]
        plot_single_traj(ax, ep, full_title)
    except Exception as e:
        print(f"[WARNING] Failed to load scen_id={scen_id}: {e}")
        axes[row][col].text(0.5, 0.5, f"scen {scen_id}\nNot found", 
                           ha="center", va="center", transform=axes[row][col].transAxes)

# === 统一四个子图的坐标范围 ===
all_x, all_y = [], []
for _, _, scen_id, _ in cases:
    try:
        ep = load_episode("gs", scen_id)
        xs, ys, gx, gy = extract_xy(ep)
        all_x.extend(xs)
        all_y.extend(ys)
    except:
        continue

if all_x and all_y:
    margin = 2.0
    x_min, x_max = min(all_x) - margin, max(all_x) + margin
    y_min, y_max = min(all_y) - margin, max(all_y) + margin
    
    for ax in axes.ravel():
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)

# 统一 legend（只放一份在上方中间）
handles, labels = axes[0][0].get_legend_handles_labels()
if handles:
    fig.legend(handles, labels, loc="upper center",
               ncol=3, fontsize=9, frameon=False)

fig.tight_layout(rect=[0, 0, 1, 0.93])

# 保存多种格式
output_dir = Path("results/figures")
output_dir.mkdir(parents=True, exist_ok=True)

fig.savefig(output_dir / "traj_gs_2x2.pdf", bbox_inches="tight", dpi=300)
fig.savefig(output_dir / "traj_gs_2x2.png", bbox_inches="tight", dpi=300)
fig.savefig(output_dir / "traj_gs_2x2.svg", bbox_inches="tight")
plt.close(fig)

print("[OK] GS 2x2轨迹图已生成: results/figures/traj_gs_2x2.{pdf,png,svg}")

