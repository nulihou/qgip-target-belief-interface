#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
方法 × 场景 对比轨迹图
展示GS / Oracle / Random三种方法在两个典型场景下的轨迹对比
"""

import json
import matplotlib.pyplot as plt
from pathlib import Path

# === 路径设置：轨迹 jsonl 所在目录 ===
BASE_DIR = Path("visualization_data/trajectory_eval")

def load_episode(mode, scen_id):
    """从对应 jsonl 中找到指定场景的完整 episode"""
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
    """从 episode 提取 2D 坐标，可选是否平移到目标原点"""
    traj = ep.get("trajectory", [])
    if not traj:
        return [], [], 0.0, 0.0
    
    xs = [p.get("x", 0.0) for p in traj]
    ys = [p.get("y", 0.0) for p in traj]
    
    # 获取目标位置
    target_pos = ep.get("target_position", {})
    if not target_pos:
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

def plot_triple_for_scene(fig, row_idx, scen_id, share_limits=True):
    """
    在同一行画一个场景下的三种方法：GS / Oracle / Random
    fig: matplotlib Figure
    row_idx: 0 或 1，表示第几行
    scen_id: 要展示的场景 id
    """
    modes = ["gs", "oracle", "random"]
    titles = ["GS-LCORGNet", "Oracle", "Random"]
    colors = ['#2E86AB', '#6C757D', '#E63946']  # 蓝色、灰色、红色
    
    axs = []
    all_x, all_y = [], []
    
    for col_idx, (mode, title, color) in enumerate(zip(modes, titles, colors)):
        ax = fig.add_subplot(2, 3, row_idx * 3 + col_idx + 1)
        
        try:
            ep = load_episode(mode, scen_id)
            xs, ys, gx, gy = extract_xy(ep)
            
            if xs and ys:
                ax.plot(xs, ys, linewidth=1.5, color=color, alpha=0.8)
                ax.scatter(xs[0], ys[0], marker="o", s=20, color='#28A745', zorder=5)
                ax.scatter(xs[-1], ys[-1], marker="s", s=24, color='#E63946', zorder=5)
                ax.scatter(gx, gy, marker="*", s=40, color='#FFC107', zorder=5)
                
                # 8m success radius
                circle = plt.Circle((gx, gy), 8.0, fill=False,
                                    linestyle="--", linewidth=1.0, color='gray', alpha=0.5)
                ax.add_patch(circle)
                
                all_x.extend(xs)
                all_y.extend(ys)
            else:
                ax.text(0.5, 0.5, "No trajectory", ha="center", va="center", 
                       transform=ax.transAxes)
            
            ax.set_aspect("equal", adjustable="box")
            ax.set_xticks([])
            ax.set_yticks([])
            
            success_8m = ep.get('success_8m', False)
            final_dist = ep.get('final_dist', 0.0)
            subtitle = (
                f"{title} | scen {scen_id} | "
                f"success@8m={success_8m} | final={final_dist:.1f}m"
            )
            ax.set_title(subtitle, fontsize=9)
            axs.append(ax)
            
        except Exception as e:
            print(f"[WARNING] Failed to load {mode} scen_id={scen_id}: {e}")
            ax.text(0.5, 0.5, f"{title}\nscen {scen_id}\nNot found", 
                   ha="center", va="center", transform=ax.transAxes)
            ax.set_title(f"{title} | scen {scen_id} | N/A", fontsize=9)
            axs.append(ax)
    
    # 这一行三个子图共享坐标范围
    if share_limits and all_x and all_y:
        margin = 2.0
        x_min, x_max = min(all_x) - margin, max(all_x) + margin
        y_min, y_max = min(all_y) - margin, max(all_y) + margin
        
        for ax in axs:
            ax.set_xlim(x_min, x_max)
            ax.set_ylim(y_min, y_max)

# === 2) 方法 × 场景 对比图 ===
fig = plt.figure(figsize=(9, 6), dpi=300)

# 第一行：scen 8，典型"选对+成功"场景
plot_triple_for_scene(fig, row_idx=0, scen_id=8)

# 第二行：scen 0，典型"选对但失败"场景
plot_triple_for_scene(fig, row_idx=1, scen_id=0)

fig.tight_layout()

# 保存多种格式
output_dir = Path("results/figures")
output_dir.mkdir(parents=True, exist_ok=True)

fig.savefig(output_dir / "traj_method_vs_scene.pdf", bbox_inches="tight", dpi=300)
fig.savefig(output_dir / "traj_method_vs_scene.png", bbox_inches="tight", dpi=300)
fig.savefig(output_dir / "traj_method_vs_scene.svg", bbox_inches="tight")
plt.close(fig)

print("[OK] 方法×场景对比轨迹图已生成: results/figures/traj_method_vs_scene.{pdf,png,svg}")

