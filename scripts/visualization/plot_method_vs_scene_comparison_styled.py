#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
精修版：方法 × 场景 对比轨迹图（顶会风格）
展示GS / Oracle / Random三种方法在两个典型场景下的轨迹对比
"""

import json
import sys
from pathlib import Path
import matplotlib as mpl
import matplotlib.pyplot as plt

# 添加路径以便导入
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 应用全局样式
def set_paper_style():
    """顶会/SCI 风格的全局样式设置"""
    mpl.rcParams.update({
        "figure.figsize": (3.0, 3.0),
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "figure.autolayout": False,
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "axes.unicode_minus": False,
        "axes.linewidth": 0.8,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "xtick.labelsize": 8,
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "legend.fontsize": 8,
        "legend.frameon": False,
        "axes.grid": False,
        "lines.linewidth": 1.4,
        "lines.markersize": 4,
    })

# 统一颜色方案
COLORS = {
    "traj":    "#222222",   # 轨迹线
    "start":   "#1f77b4",   # 起点
    "end":     "#ff7f0e",   # 终点
    "goal_ok": "#2ca02c",   # 目标（选对）- 绿色
    "goal_bad": "#d62728",  # 目标（选错）- 红色
    "radius":  "#7f7f7f",   # 8m 半径
}

set_paper_style()

# === 路径设置 ===
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
    raise ValueError(f"scen_id={scen_id} not found in mode={mode}")

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

def style_axes(ax):
    """统一坐标轴样式"""
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)
        spine.set_color("#bbbbbb")

def plot_triple_for_scene(fig, row_idx, scen_id, show_radius=True, radius=8.0):
    """在同一行画一个场景下的三种方法：GS / Oracle / Random"""
    modes = ["gs", "oracle", "random"]
    titles = ["GS-LCORGNet", "Oracle", "Random"]
    
    axs = []
    all_x, all_y = [], []
    
    # 先画三种方法
    for col_idx, (mode, title) in enumerate(zip(modes, titles)):
        ax = fig.add_subplot(2, 3, row_idx * 3 + col_idx + 1)
        
        try:
            ep = load_episode(mode, scen_id)
            xs, ys, gx, gy = extract_xy(ep)
            
            if not xs or not ys:
                ax.text(0.5, 0.5, "No trajectory", ha="center", va="center", 
                       transform=ax.transAxes, fontsize=8)
                style_axes(ax)
                axs.append(ax)
                continue
            
            # 主轨迹线
            ax.plot(xs, ys, color=COLORS["traj"], linewidth=1.6,
                    solid_joinstyle="round", solid_capstyle="round", alpha=0.95)
            
            # 起点 / 终点
            ax.scatter(xs[0], ys[0], marker="o", s=18,
                       edgecolor="white", linewidths=0.4,
                       facecolor=COLORS["start"], zorder=3)
            ax.scatter(xs[-1], ys[-1], marker="s", s=22,
                       edgecolor="white", linewidths=0.4,
                       facecolor=COLORS["end"], zorder=3)
            
            # 目标：颜色根据 gs_correct 来区分（选对=绿色，选错=红色）
            gs_correct = ep.get("gs_correct", False)
            goal_color = COLORS["goal_ok"] if gs_correct else COLORS["goal_bad"]
            ax.scatter(gx, gy, marker="*", s=40,
                       edgecolor="white", linewidths=0.5,
                       facecolor=goal_color, zorder=4)
            
            # 可选：同样画 8m 半径圆（让两个图风格统一）
            if show_radius:
                circle = plt.Circle(
                    (gx, gy), radius,
                    fill=False,
                    linestyle=(0, (3, 3)),
                    linewidth=0.8,
                    edgecolor=COLORS["radius"],
                    alpha=0.8,
                )
                ax.add_patch(circle)
            
            # 标题：上方法名，下简单指标（含多候选信息）
            success_8m = ep.get('success_8m', False)
            final_dist = ep.get('final_dist', 0.0)
            k = ep.get("num_candidates", 0)
            gt_idx = ep.get("target_idx_gt", -1)
            chosen_idx = ep.get("chosen_idx_graph") or ep.get("chosen_idx", -1)
            
            subtitle = (
                f"scene {scen_id} | "
                f"succ@8m={success_8m} | final={final_dist:.1f}m\n"
                f"k={k}, gt={gt_idx}, chosen={chosen_idx}"
            )
            ax.set_title(f"{title}\n{subtitle}", fontsize=8.5, pad=4)
            
            style_axes(ax)
            axs.append(ax)
            
            all_x.extend(xs)
            all_y.extend(ys)
            
        except Exception as e:
            print(f"[WARNING] Failed to load {mode} scen_id={scen_id}: {e}")
            ax.text(0.5, 0.5, f"{title}\nscene {scen_id}\nNot found", 
                   ha="center", va="center", transform=ax.transAxes, fontsize=8)
            ax.set_title(f"{title}\nscene {scen_id} | N/A", fontsize=8.5, pad=4)
            style_axes(ax)
            axs.append(ax)
    
    # 该行三幅图共享坐标范围
    if all_x and all_y:
        margin = 2.0
        x_min, x_max = min(all_x) - margin, max(all_x) + margin
        y_min, y_max = min(all_y) - margin, max(all_y) + margin
        
        for ax in axs:
            ax.set_xlim(x_min, x_max)
            ax.set_ylim(y_min, y_max)

# === 画图 ===
fig = plt.figure(figsize=(7.0, 4.5))

# Row 0: scene 8 (典型成功)
plot_triple_for_scene(fig, row_idx=0, scen_id=8)

# Row 1: scene 0 (典型失败)
plot_triple_for_scene(fig, row_idx=1, scen_id=0)

fig.tight_layout()

# 保存多种格式
output_dir = Path("results/figures")
output_dir.mkdir(parents=True, exist_ok=True)

fig.savefig(output_dir / "traj_method_vs_scene_styled.pdf", bbox_inches="tight", dpi=300)
fig.savefig(output_dir / "traj_method_vs_scene_styled.png", bbox_inches="tight", dpi=300)
fig.savefig(output_dir / "traj_method_vs_scene_styled.svg", bbox_inches="tight")
plt.close(fig)

print("[OK] 精修版方法×场景对比轨迹图已生成: results/figures/traj_method_vs_scene_styled.{pdf,png,svg}")

