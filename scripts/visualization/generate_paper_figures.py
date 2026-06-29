#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成论文所需的所有可视化图表

包括：
1. 语义导航性能多指标对比柱状图（表3）⭐⭐⭐
2. 2×2表热力图（表5）⭐⭐⭐
3. Protocol-level目标选择对比柱状图（表2）
4. 离线GS性能分组对比柱状图（表1）
5. Ranking Loss Ablation对比图（表6）
6. 难度分组鲁棒性分析图（表7）
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns
from pathlib import Path
from typing import Dict, List, Any, Tuple

# 设置中文字体和样式
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
plt.style.use('seaborn-v0_8-paper')
sns.set_palette("husl")

# 设置输出目录
output_dir = Path("results/figures")
output_dir.mkdir(parents=True, exist_ok=True)

# 设置论文级参数
DPI = 300
FIG_SIZE_SINGLE = (3.5, 2.5)  # 单栏宽度（英寸）
FIG_SIZE_DOUBLE = (7.0, 3.0)  # 双栏宽度（英寸）


# ============================================================================
# 图1: 语义导航性能多指标对比柱状图（表3）⭐⭐⭐
# ============================================================================

def plot_semantic_nav_performance():
    """生成语义导航性能多指标对比柱状图"""
    
    methods = ['Random', 'GS (LCORGNet)', 'Oracle']
    gs_at_1 = [46.7, 93.3, 100.0]
    sem_navsucc_8m = [23.3, 50.0, 60.0]
    sem_navsucc_4m = [3.3, 10.0, 6.7]
    
    x = np.arange(len(methods))
    width = 0.25
    
    fig, ax = plt.subplots(figsize=FIG_SIZE_DOUBLE, dpi=DPI)
    
    bars1 = ax.bar(x - width, gs_at_1, width, label='GS@1 (proto)', color='#3498db', alpha=0.8)
    bars2 = ax.bar(x, sem_navsucc_8m, width, label='SemNavSucc@8m', color='#2ecc71', alpha=0.8)
    bars3 = ax.bar(x + width, sem_navsucc_4m, width, label='SemNavSucc@4m', color='#e74c3c', alpha=0.8)
    
    # 添加数值标签
    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}%',
                   ha='center', va='bottom', fontsize=8)
    
    ax.set_xlabel('Method', fontsize=11)
    ax.set_ylabel('Performance (%)', fontsize=11)
    ax.set_title('Semantic-Aware Navigation Performance', fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(methods)
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_ylim([0, 110])
    
    plt.tight_layout()
    plt.savefig(output_dir / 'semantic_nav_performance.png', dpi=DPI, bbox_inches='tight')
    plt.savefig(output_dir / 'semantic_nav_performance.pdf', bbox_inches='tight')
    plt.savefig(output_dir / 'semantic_nav_performance.svg', bbox_inches='tight')
    plt.close()
    
    print("[OK] 生成图1: 语义导航性能多指标对比柱状图")


# ============================================================================
# 图2: 2×2表热力图（表5）⭐⭐⭐
# ============================================================================

def plot_2x2_heatmap():
    """生成2×2表热力图"""
    
    # 三个模式的数据
    data_gs = np.array([[15, 13], [1, 1]])
    data_random = np.array([[7, 7], [14, 2]])
    data_oracle = np.array([[18, 12], [0, 0]])
    
    fig, axes = plt.subplots(1, 3, figsize=(10, 3), dpi=DPI)
    
    for idx, (data, title) in enumerate([
        (data_gs, 'GS Mode'),
        (data_random, 'Random Mode'),
        (data_oracle, 'Oracle Mode')
    ]):
        ax = axes[idx]
        
        # 创建热力图
        im = ax.imshow(data, cmap='YlOrRd', aspect='auto', vmin=0, vmax=20)
        
        # 设置刻度
        ax.set_xticks([0, 1])
        ax.set_xticklabels(['Success@8m', 'Fail@8m'], fontsize=9)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(['Correct', 'Wrong'], fontsize=9)
        
        # 添加数值
        for i in range(2):
            for j in range(2):
                text = ax.text(j, i, f'{data[i, j]}',
                             ha="center", va="center", color="black", fontsize=11, fontweight='bold')
        
        ax.set_title(title, fontsize=10, fontweight='bold')
        
        # 添加颜色条
        if idx == 2:
            cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label('Episodes', fontsize=8)
    
    plt.suptitle('2×2 Contingency Table: Selection × Navigation Success', 
                 fontsize=12, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_dir / '2x2_heatmap.png', dpi=DPI, bbox_inches='tight')
    plt.savefig(output_dir / '2x2_heatmap.pdf', bbox_inches='tight')
    plt.savefig(output_dir / '2x2_heatmap.svg', bbox_inches='tight')
    plt.close()
    
    print("[OK] 生成图2: 2x2表热力图")


# ============================================================================
# 图3: Protocol-level目标选择对比柱状图（表2）
# ============================================================================

def plot_protocol_selection():
    """生成Protocol-level目标选择对比柱状图"""
    
    methods = ['Oracle', 'GS (LCORGNet)', 'Random', 'Heuristic (Nearest)']
    gs_at_1 = [100.0, 93.3, 46.7, 6.7]
    colors = ['#95a5a6', '#2ecc71', '#e74c3c', '#f39c12']
    
    fig, ax = plt.subplots(figsize=FIG_SIZE_SINGLE, dpi=DPI)
    
    bars = ax.bar(methods, gs_at_1, color=colors, alpha=0.8)
    
    # 突出GS方法
    bars[1].set_edgecolor('black')
    bars[1].set_linewidth(2)
    
    # 添加数值标签
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{height:.1f}%',
               ha='center', va='bottom', fontsize=9)
    
    ax.set_xlabel('Method', fontsize=11)
    ax.set_ylabel('GS@1 (proto) (%)', fontsize=11)
    ax.set_title('Protocol-level Target Selection', fontsize=12, fontweight='bold')
    ax.set_ylim([0, 110])
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    plt.xticks(rotation=15, ha='right')
    plt.tight_layout()
    plt.savefig(output_dir / 'protocol_selection.png', dpi=DPI, bbox_inches='tight')
    plt.savefig(output_dir / 'protocol_selection.pdf', bbox_inches='tight')
    plt.savefig(output_dir / 'protocol_selection.svg', bbox_inches='tight')
    plt.close()
    
    print("[OK] 生成图3: Protocol-level目标选择对比柱状图")


# ============================================================================
# 图4: 离线GS性能分组对比柱状图（表1）
# ============================================================================

def plot_offline_grouped():
    """生成离线GS性能分组对比柱状图"""
    
    # 按候选数分组
    k_categories = ['K=2', 'K=3']
    k_values = [99.0, 98.0]
    
    # 按距离分组
    dist_categories = ['30-40m', '40-50m', '50-60m']
    dist_values = [99.1, 96.4, 97.1]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=FIG_SIZE_DOUBLE, dpi=DPI)
    
    # 子图1: 按候选数分组
    bars1 = ax1.bar(k_categories, k_values, color=['#3498db', '#2ecc71'], alpha=0.8)
    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%',
                ha='center', va='bottom', fontsize=9)
    ax1.set_ylabel('GS@1 (%)', fontsize=11)
    ax1.set_title('By #Candidates', fontsize=11, fontweight='bold')
    ax1.set_ylim([95, 100])
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    
    # 子图2: 按距离分组
    bars2 = ax2.bar(dist_categories, dist_values, color=['#e74c3c', '#f39c12', '#9b59b6'], alpha=0.8)
    for bar in bars2:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%',
                ha='center', va='bottom', fontsize=9)
    ax2.set_ylabel('GS@1 (%)', fontsize=11)
    ax2.set_title('By Distance Range', fontsize=11, fontweight='bold')
    ax2.set_ylim([95, 100])
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    
    plt.suptitle('Offline GS Performance (Grouped)', fontsize=12, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_dir / 'offline_grouped.png', dpi=DPI, bbox_inches='tight')
    plt.savefig(output_dir / 'offline_grouped.pdf', bbox_inches='tight')
    plt.savefig(output_dir / 'offline_grouped.svg', bbox_inches='tight')
    plt.close()
    
    print("[OK] 生成图4: 离线GS性能分组对比柱状图")


# ============================================================================
# 图5: Ranking Loss Ablation对比图（表6）
# ============================================================================

def plot_ranking_loss_ablation():
    """生成Ranking Loss Ablation对比图"""
    
    models = ['Ours (Full)', '− Ranking']
    metrics = {
        'L1 GS@1\n(offline)': [98.4, 99.2],
        'Proto\nGS@1': [93.3, 93.3],
        'NavSucc\n@8m': [53.3, 50.0],
        'SemNavSucc\n@8m': [50.0, 46.7],
        'Avg min\ndist (m)': [13.59, 14.50]
    }
    
    x = np.arange(len(models))
    width = 0.15
    num_metrics = len(metrics)
    
    fig, ax = plt.subplots(figsize=FIG_SIZE_DOUBLE, dpi=DPI)
    
    colors = plt.cm.Set3(np.linspace(0, 1, num_metrics))
    
    for idx, (metric_name, values) in enumerate(metrics.items()):
        offset = (idx - num_metrics/2 + 0.5) * width
        bars = ax.bar(x + offset, values, width, label=metric_name, 
                     color=colors[idx], alpha=0.8)
        
        # 添加数值标签
        for bar in bars:
            height = bar.get_height()
            if 'dist' in metric_name.lower():
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.2f}',
                       ha='center', va='bottom', fontsize=7)
            else:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}',
                       ha='center', va='bottom', fontsize=7)
    
    ax.set_xlabel('Model', fontsize=11)
    ax.set_ylabel('Performance', fontsize=11)
    ax.set_title('Effect of Ranking Loss', fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend(loc='upper right', fontsize=8, ncol=2)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    plt.savefig(output_dir / 'ranking_loss_ablation.png', dpi=DPI, bbox_inches='tight')
    plt.savefig(output_dir / 'ranking_loss_ablation.pdf', bbox_inches='tight')
    plt.savefig(output_dir / 'ranking_loss_ablation.svg', bbox_inches='tight')
    plt.close()
    
    print("[OK] 生成图5: Ranking Loss Ablation对比图")


# ============================================================================
# 图6: 难度分组鲁棒性分析图（表7）
# ============================================================================

def plot_difficulty_robustness():
    """生成难度分组鲁棒性分析图"""
    
    # 加载数据
    data_path = Path("results/proto_main_eval/difficulty_robustness_analysis.json")
    if not data_path.exists():
        print("[WARNING] 文件不存在: " + str(data_path))
        return
    
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    distances = ['30-40m', '40-50m']
    methods = ['GS', 'Random', 'Oracle']
    
    semantic_navsucc = [
        [data['by_distance']['30–40m']['gs']['semantic_navsucc_8m'],
         data['by_distance']['40–50m']['gs']['semantic_navsucc_8m']],
        [data['by_distance']['30–40m']['random']['semantic_navsucc_8m'],
         data['by_distance']['40–50m']['random']['semantic_navsucc_8m']],
        [data['by_distance']['30–40m']['oracle']['semantic_navsucc_8m'],
         data['by_distance']['40–50m']['oracle']['semantic_navsucc_8m']]
    ]
    
    x = np.arange(len(distances))
    width = 0.25
    
    fig, ax = plt.subplots(figsize=FIG_SIZE_SINGLE, dpi=DPI)
    
    colors = ['#2ecc71', '#e74c3c', '#3498db']
    for idx, (method, values) in enumerate(zip(methods, semantic_navsucc)):
        bars = ax.bar(x + idx*width, values, width, label=method, 
                     color=colors[idx], alpha=0.8)
        
        # 添加数值标签
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}%',
                   ha='center', va='bottom', fontsize=8)
    
    ax.set_xlabel('Distance Range', fontsize=11)
    ax.set_ylabel('Semantic-NavSucc@8m (%)', fontsize=11)
    ax.set_title('Robustness Analysis by Distance', fontsize=12, fontweight='bold')
    ax.set_xticks(x + width)
    ax.set_xticklabels(distances)
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_ylim([0, 75])
    
    plt.tight_layout()
    plt.savefig(output_dir / 'difficulty_robustness.png', dpi=DPI, bbox_inches='tight')
    plt.savefig(output_dir / 'difficulty_robustness.pdf', bbox_inches='tight')
    plt.savefig(output_dir / 'difficulty_robustness.svg', bbox_inches='tight')
    plt.close()
    
    print("[OK] 生成图6: 难度分组鲁棒性分析图")


# ============================================================================
# 主函数
# ============================================================================

def main():
    print("="*60)
    print("生成论文所需的所有可视化图表")
    print("="*60)
    
    # 生成所有图表
    plot_semantic_nav_performance()      # 图1 ⭐⭐⭐
    plot_2x2_heatmap()                   # 图2 ⭐⭐⭐
    plot_protocol_selection()           # 图3
    plot_offline_grouped()               # 图4
    plot_ranking_loss_ablation()         # 图5
    plot_difficulty_robustness()         # 图6
    
    print("\n" + "="*60)
    print(f"[OK] 所有图表生成完成！")
    print(f"输出目录: {output_dir}")
    print(f"共生成 6 张图表（PNG + PDF格式）")
    print("="*60)


if __name__ == '__main__':
    main()

