#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
精修版：GS 2×2 行为轨迹图（顶会风格）
展示四种"目标选择 × 导航结果"组合下的典型轨迹
"""

import json
import sys
from pathlib import Path
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

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
        "ytick.labelsize": 8,
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

def plot_candidate_inset(ax, ep, inset_pos=(0.95, 0.95), inset_size=0.15):
    """
    在子图右上角绘制候选目标示意图（概念化）
    
    Args:
        ax: matplotlib axes
        ep: episode数据
        inset_pos: inset位置 (x, y) 在axes坐标系中
        inset_size: inset大小（占axes的比例）
    """
    k = ep.get("num_candidates", 0)
    gt_idx = ep.get("target_idx_gt", -1)
    chosen_idx = ep.get("chosen_idx_graph") or ep.get("chosen_idx", -1)
    gs_correct = ep.get("gs_correct", False)
    
    if k <= 1:
        return  # 不需要显示
    
    # 创建inset axes（右上角）
    inset_ax = inset_axes(ax, width=f"{inset_size*100}%", height=f"{inset_size*100}%",
                          loc='upper right', borderpad=0)
    
    # 在inset中画一个圆环，均匀分布候选点
    center = (0.5, 0.5)
    radius_ring = 0.35
    
    # 画圆环
    circle_ring = plt.Circle(center, radius_ring, fill=False, 
                            linestyle='--', linewidth=0.8, 
                            color='#888888', alpha=0.6, transform=inset_ax.transAxes)
    inset_ax.add_patch(circle_ring)
    
    # 计算候选点的角度（均匀分布）
    angles = np.linspace(0, 2*np.pi, k, endpoint=False)
    
    for i, angle in enumerate(angles):
        # 候选点在圆环上的位置
        x = center[0] + radius_ring * np.cos(angle)
        y = center[1] + radius_ring * np.sin(angle)
        
        # 候选点索引（从1开始）
        cand_idx = i + 1
        
        # 颜色：GT=绿色，chosen=蓝色，其他=灰色
        if cand_idx == gt_idx + 1:  # gt_idx从0开始，显示从1开始
            color = COLORS["goal_ok"]  # 绿色
            marker = "o"
            size = 30
            edgecolor = "white"
            edgewidth = 0.8
        elif cand_idx == chosen_idx + 1:  # chosen_idx从0开始
            color = "#1f77b4" if gs_correct else COLORS["goal_bad"]  # 蓝色（选对）或红色（选错）
            marker = "s"
            size = 35
            edgecolor = "white"
            edgewidth = 1.0
        else:
            color = "#cccccc"  # 灰色
            marker = "o"
            size = 20
            edgecolor = "#888888"
            edgewidth = 0.5
        
        # 绘制候选点
        inset_ax.scatter(x, y, marker=marker, s=size,
                        edgecolor=edgecolor, linewidths=edgewidth,
                        facecolor=color, zorder=3, transform=inset_ax.transAxes)
        
        # 标注索引
        label_x = center[0] + (radius_ring + 0.08) * np.cos(angle)
        label_y = center[1] + (radius_ring + 0.08) * np.sin(angle)
        inset_ax.text(label_x, label_y, str(cand_idx), 
                     ha='center', va='center', fontsize=6,
                     transform=inset_ax.transAxes, weight='bold')
    
    # 设置inset样式
    inset_ax.set_xlim(0, 1)
    inset_ax.set_ylim(0, 1)
    inset_ax.set_xticks([])
    inset_ax.set_yticks([])
    inset_ax.set_aspect('equal')
    for spine in inset_ax.spines.values():
        spine.set_linewidth(0.5)
        spine.set_color("#aaaaaa")
        spine.set_alpha(0.5)

def plot_single_traj(ax, ep, title, show_radius=True, radius=8.0, show_inset=True):
    """在给定 ax 上画一个 episode 的轨迹图（俯视）"""
    xs, ys, gx, gy = extract_xy(ep, center_to_goal=True)
    
    if not xs or not ys:
        ax.text(0.5, 0.5, "No trajectory data", ha="center", va="center", 
               transform=ax.transAxes, fontsize=8)
        ax.set_title(title, fontsize=8.5, pad=4)
        return
    
    # 轨迹主线：略微透明，给起点终点留层次
    ax.plot(xs, ys, color=COLORS["traj"], linewidth=1.6,
            solid_joinstyle="round", solid_capstyle="round", alpha=0.95)
    
    # 起点 / 终点
    ax.scatter(xs[0], ys[0], marker="o", s=18,
               edgecolor="white", linewidths=0.4,
               facecolor=COLORS["start"], zorder=3, label="Start")
    ax.scatter(xs[-1], ys[-1], marker="s", s=22,
               edgecolor="white", linewidths=0.4,
               facecolor=COLORS["end"], zorder=3, label="End")
    
    # 目标：颜色根据 gs_correct 来区分（选对=绿色，选错=红色）
    gs_correct = ep.get("gs_correct", False)
    goal_color = COLORS["goal_ok"] if gs_correct else COLORS["goal_bad"]
    ax.scatter(gx, gy, marker="*", s=40,
               edgecolor="white", linewidths=0.5,
               facecolor=goal_color, zorder=4, label="Goal")
    
    # 成功半径：细虚线，淡一点
    if show_radius:
        circle = plt.Circle(
            (gx, gy), radius,
            fill=False,
            linestyle=(0, (3, 3)),  # 自定义虚线 pattern
            linewidth=0.8,
            edgecolor=COLORS["radius"],
            alpha=0.8,
        )
        ax.add_patch(circle)
    
    # 坐标轴：无刻度、等比例、小边框
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    
    # 轴边框颜色淡一点
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)
        spine.set_color("#bbbbbb")
    
    ax.set_title(title, fontsize=8.5, pad=4)
    
    # 绘制候选目标示意图（inset）
    if show_inset:
        plot_candidate_inset(ax, ep)

# === GS 2×2 ===
# 重新选择的更合适的episode（保证轨迹清晰）
cases = [
    (0, 0, 22, "Correct & Success"),  # scen 22: 选对+成功
    (0, 1, 5,  "Correct & Fail"),     # scen 5: 选对+失败
    (1, 0, 6,  "Wrong & Success"),    # scen 6: 选错+成功
    (1, 1, 24, "Wrong & Fail"),       # scen 24: 选错+失败
]

fig, axes = plt.subplots(2, 2, figsize=(4.6, 4.6))

# 收集坐标范围以统一轴范围
all_x, all_y = [], []
for _, _, scen_id, _ in cases:
    try:
        ep_tmp = load_episode("gs", scen_id)
        xs_tmp, ys_tmp, _, _ = extract_xy(ep_tmp)
        all_x.extend(xs_tmp)
        all_y.extend(ys_tmp)
    except:
        continue

if all_x and all_y:
    margin = 2.0
    x_min, x_max = min(all_x) - margin, max(all_x) + margin
    y_min, y_max = min(all_y) - margin, max(all_y) + margin
else:
    x_min, x_max, y_min, y_max = -50, 50, -50, 50

for row, col, scen_id, label in cases:
    try:
        ep = load_episode("gs", scen_id)
        
        # 提取多候选信息
        k = ep.get("num_candidates", 0)
        gt_idx = ep.get("target_idx_gt", -1)
        chosen_idx = ep.get("chosen_idx_graph") or ep.get("chosen_idx", -1)
        
        # 标题包含多候选信息
        subtitle = (
            f"scene {scen_id}, step={ep.get('steps', 0)}, "
            f"start={ep.get('start_dist', 0.0):.1f}m, final={ep.get('final_dist', 0.0):.1f}m\n"
            f"{k} candidates, gt={gt_idx}, chosen={chosen_idx}"
        )
        full_title = f"{label}\n{subtitle}"
        
        ax = axes[row][col]
        plot_single_traj(ax, ep, full_title)
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
    except Exception as e:
        print(f"[WARNING] Failed to load scen_id={scen_id}: {e}")
        axes[row][col].text(0.5, 0.5, f"scene {scen_id}\nNot found", 
                           ha="center", va="center", 
                           transform=axes[row][col].transAxes, fontsize=8)

# 只在整体图上放一份 legend（上方居中）
handles, labels = axes[0][0].get_legend_handles_labels()
if handles:
    fig.legend(handles, labels, loc="upper center", ncol=3,
               frameon=False, borderaxespad=0.2, handlelength=1.5,
               handletextpad=0.6, columnspacing=1.5)

fig.tight_layout(rect=[0, 0, 1, 0.90])

# 保存多种格式
output_dir = Path("results/figures")
output_dir.mkdir(parents=True, exist_ok=True)

fig.savefig(output_dir / "traj_gs_2x2_styled_multicand.pdf", bbox_inches="tight", dpi=300)
fig.savefig(output_dir / "traj_gs_2x2_styled_multicand.png", bbox_inches="tight", dpi=300)
fig.savefig(output_dir / "traj_gs_2x2_styled_multicand.svg", bbox_inches="tight")
plt.close(fig)

print("[OK] 精修版GS 2x2轨迹图（含多候选信息）已生成: results/figures/traj_gs_2x2_styled_multicand.{pdf,png,svg}")

