#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成轨迹对比图

从trajectory_eval日志中提取代表性episodes，生成2×2四象限轨迹对比图
"""

import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# 设置输出目录
output_dir = Path("results/figures")
output_dir.mkdir(parents=True, exist_ok=True)

DPI = 300


def load_jsonl(path: Path) -> Dict[int, Dict[str, Any]]:
    """加载JSONL文件，返回以scen_id为key的字典"""
    episodes = {}
    if not path.exists():
        print(f"[WARNING] File not found: {path}")
        return episodes
    
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                scen_id = rec.get("scen_id", rec.get("episode"))
                if scen_id is not None:
                    episodes[scen_id] = rec
            except json.JSONDecodeError as e:
                continue
    
    return episodes


def extract_trajectory(episode_data: Dict[str, Any]) -> List[Tuple[float, float]]:
    """提取轨迹点"""
    traj = episode_data.get("trajectory", [])
    if not traj:
        return []
    
    points = []
    for point in traj:
        if isinstance(point, dict):
            x = point.get("x", 0.0)
            y = point.get("y", 0.0)
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            x, y = point[0], point[1]
        else:
            continue
        points.append((float(x), float(y)))
    
    return points


def plot_single_trajectory(ax, traj: List[Tuple[float, float]], 
                           episode_data: Dict[str, Any],
                           color: str, label: str, title: str):
    """在子图上绘制单个轨迹"""
    if not traj or len(traj) == 0:
        ax.text(0.5, 0.5, 'No trajectory data', 
                ha='center', va='center', transform=ax.transAxes)
        ax.set_title(title, fontsize=10, fontweight='bold')
        return
    
    xs = [p[0] for p in traj]
    ys = [p[1] for p in traj]
    
    # 绘制轨迹
    ax.plot(xs, ys, color=color, linewidth=2, alpha=0.7, label=label, zorder=1)
    
    # 标记起点
    ax.plot(xs[0], ys[0], 'go', markersize=8, markeredgewidth=1.5,
            markeredgecolor='darkgreen', zorder=3, label='Start')
    
    # 标记终点
    ax.plot(xs[-1], ys[-1], 'rs', markersize=8, markeredgewidth=1.5,
            markeredgecolor='darkred', zorder=3, label='End')
    
    # 添加信息文本
    chosen = episode_data.get("chosen_idx_graph") or episode_data.get("chosen_idx")
    target = episode_data.get("target_idx_gt")
    is_correct = (chosen is not None and target is not None and chosen == target)
    success_8m = episode_data.get("success_8m", False)
    min_dist = episode_data.get("min_dist", 0.0)
    
    info_text = f"Min dist: {min_dist:.2f}m\n"
    info_text += f"Correct: {'Yes' if is_correct else 'No'}\n"
    info_text += f"Success@8m: {'Yes' if success_8m else 'No'}"
    
    ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
            verticalalignment='top', fontsize=8,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='wheat', alpha=0.8),
            zorder=4)
    
    ax.set_title(title, fontsize=10, fontweight='bold')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_aspect('equal', adjustable='box')
    ax.legend(loc='upper right', fontsize=7)


def plot_2x2_trajectory_comparison():
    """生成2×2四象限轨迹对比图"""
    
    # 加载数据
    gs_path = Path("logs_v2/proto_main_eval/trajectory_eval/gs_proto_driven.jsonl")
    random_path = Path("logs_v2/proto_main_eval/trajectory_eval/random_proto_driven.jsonl")
    
    gs_episodes = load_jsonl(gs_path)
    random_episodes = load_jsonl(random_path)
    
    if not gs_episodes or not random_episodes:
        print("[ERROR] 无法加载轨迹数据")
        return
    
    # 找到代表性episodes（基于2×2表）
    representatives = {
        'correct_success': None,    # 选对+成功
        'correct_fail': None,       # 选对+失败
        'wrong_success': None,      # 选错+成功
        'wrong_fail': None          # 选错+失败
    }
    
    # 从GS数据中找到代表性episodes
    for scen_id, gs_data in gs_episodes.items():
        chosen = gs_data.get("chosen_idx_graph") or gs_data.get("chosen_idx")
        target = gs_data.get("target_idx_gt")
        is_correct = (chosen is not None and target is not None and chosen == target)
        success_8m = gs_data.get("success_8m", False)
        
        if is_correct and success_8m and representatives['correct_success'] is None:
            representatives['correct_success'] = (scen_id, gs_data)
        elif is_correct and not success_8m and representatives['correct_fail'] is None:
            representatives['correct_fail'] = (scen_id, gs_data)
        elif not is_correct and success_8m and representatives['wrong_success'] is None:
            representatives['wrong_success'] = (scen_id, gs_data)
        elif not is_correct and not success_8m and representatives['wrong_fail'] is None:
            representatives['wrong_fail'] = (scen_id, gs_data)
        
        if all(v is not None for v in representatives.values()):
            break
    
    # 创建2×2子图
    fig, axes = plt.subplots(2, 2, figsize=(14, 14), dpi=DPI)
    fig.suptitle('2×2 Trajectory Comparison: Selection Correctness × Navigation Success@8m', 
                 fontsize=14, fontweight='bold', y=0.98)
    
    # 绘制每个象限
    categories = [
        ('correct_success', 'Correct + Success', 'blue', 'upper left'),
        ('correct_fail', 'Correct + Fail', 'orange', 'upper right'),
        ('wrong_success', 'Wrong + Success', 'red', 'lower left'),
        ('wrong_fail', 'Wrong + Fail', 'gray', 'lower right')
    ]
    
    for idx, (key, title, color, pos) in enumerate(categories):
        row = idx // 2
        col = idx % 2
        ax = axes[row, col]
        
        if representatives[key] is None:
            ax.text(0.5, 0.5, f'No representative episode\nfor {title}', 
                   ha='center', va='center', transform=ax.transAxes)
            ax.set_title(title, fontsize=10, fontweight='bold')
            continue
        
        scen_id, episode_data = representatives[key]
        traj = extract_trajectory(episode_data)
        
        plot_single_trajectory(ax, traj, episode_data, color, 'Trajectory', title)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'trajectory_2x2_comparison.png', dpi=DPI, bbox_inches='tight')
    plt.savefig(output_dir / 'trajectory_2x2_comparison.pdf', bbox_inches='tight')
    plt.savefig(output_dir / 'trajectory_2x2_comparison.svg', bbox_inches='tight')
    plt.close()
    
    print("[OK] 生成轨迹对比图: 2x2四象限图")


def plot_gs_vs_random_comparison():
    """生成GS vs Random的轨迹对比图"""
    
    # 加载数据
    gs_path = Path("logs_v2/proto_main_eval/trajectory_eval/gs_proto_driven.jsonl")
    random_path = Path("logs_v2/proto_main_eval/trajectory_eval/random_proto_driven.jsonl")
    
    gs_episodes = load_jsonl(gs_path)
    random_episodes = load_jsonl(random_path)
    
    if not gs_episodes or not random_episodes:
        print("[ERROR] 无法加载轨迹数据")
        return
    
    # 找到GS成功但Random失败的场景
    comparison_scen_id = None
    for scen_id, gs_data in gs_episodes.items():
        random_data = random_episodes.get(scen_id)
        if random_data is None:
            continue
        
        gs_correct = (gs_data.get("chosen_idx_graph") or gs_data.get("chosen_idx")) == gs_data.get("target_idx_gt")
        gs_success = gs_data.get("success_8m", False)
        random_success = random_data.get("success_8m", False)
        
        if gs_correct and gs_success and not random_success:
            comparison_scen_id = scen_id
            break
    
    if comparison_scen_id is None:
        print("[WARNING] 未找到合适的对比场景")
        return
    
    gs_data = gs_episodes[comparison_scen_id]
    random_data = random_episodes[comparison_scen_id]
    
    gs_traj = extract_trajectory(gs_data)
    random_traj = extract_trajectory(random_data)
    
    # 创建对比图
    fig, ax = plt.subplots(figsize=(12, 10), dpi=DPI)
    
    # 绘制GS轨迹
    if gs_traj:
        gs_xs = [p[0] for p in gs_traj]
        gs_ys = [p[1] for p in gs_traj]
        ax.plot(gs_xs, gs_ys, 'b-', linewidth=2.5, label='GS Trajectory', alpha=0.8, zorder=1)
        ax.plot(gs_xs[0], gs_ys[0], 'go', markersize=12, markeredgewidth=2,
                markeredgecolor='darkgreen', label='Start', zorder=3)
        ax.plot(gs_xs[-1], gs_ys[-1], 'bs', markersize=12, markeredgewidth=2,
                markeredgecolor='darkblue', label='GS End', zorder=3)
    
    # 绘制Random轨迹
    if random_traj:
        random_xs = [p[0] for p in random_traj]
        random_ys = [p[1] for p in random_traj]
        ax.plot(random_xs, random_ys, 'r--', linewidth=2.5, label='Random Trajectory', alpha=0.8, zorder=1)
        ax.plot(random_xs[-1], random_ys[-1], 'rs', markersize=12, markeredgewidth=2,
                markeredgecolor='darkred', label='Random End', zorder=3)
    
    # 添加信息
    info_text = f"Scenario ID: {comparison_scen_id}\n\n"
    info_text += f"GS: Min dist={gs_data.get('min_dist', 0):.2f}m, "
    info_text += f"Success@8m={'Yes' if gs_data.get('success_8m') else 'No'}\n"
    info_text += f"Random: Min dist={random_data.get('min_dist', 0):.2f}m, "
    info_text += f"Success@8m={'Yes' if random_data.get('success_8m') else 'No'}"
    
    ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
            verticalalignment='top', fontsize=10,
            bbox=dict(boxstyle='round,pad=0.5', facecolor='wheat', alpha=0.9),
            zorder=4)
    
    ax.set_xlabel('X (m)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Y (m)', fontsize=12, fontweight='bold')
    ax.set_title('GS vs Random Trajectory Comparison', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_aspect('equal', adjustable='box')
    
    plt.tight_layout()
    plt.savefig(output_dir / 'trajectory_gs_vs_random.png', dpi=DPI, bbox_inches='tight')
    plt.savefig(output_dir / 'trajectory_gs_vs_random.pdf', bbox_inches='tight')
    plt.savefig(output_dir / 'trajectory_gs_vs_random.svg', bbox_inches='tight')
    plt.close()
    
    print("[OK] 生成轨迹对比图: GS vs Random")


def main():
    print("="*60)
    print("生成轨迹对比图")
    print("="*60)
    
    plot_2x2_trajectory_comparison()
    plot_gs_vs_random_comparison()
    
    print("\n" + "="*60)
    print("[OK] 所有轨迹对比图生成完成！")
    print(f"输出目录: {output_dir}")
    print("="*60)


if __name__ == '__main__':
    main()

