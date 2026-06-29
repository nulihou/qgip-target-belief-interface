#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成分析类结果的可视化图表

包括：
1. GS×导航 2×2 统计的热力图/分块条形图
2. "选错+成功"空间距离分布（直方图/条形图）
3. 干净场景 vs 全体场景对比（选错+成功占比对比）
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from pathlib import Path

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# 设置输出目录
output_dir = Path("results/figures")
output_dir.mkdir(parents=True, exist_ok=True)

# ============================================================================
# 图1: GS×导航 2×2 统计的热力图和分块条形图
# ============================================================================

def plot_2x2_heatmap_and_bar():
    """绘制GS×导航2×2统计的热力图和分块条形图"""
    
    # 原始场景数据（29 episodes）
    original_data = {
        'correct_success': 6,
        'correct_fail': 11,
        'wrong_success': 7,
        'wrong_fail': 5
    }
    original_total = sum(original_data.values())
    
    # 严格场景数据（30 episodes）
    strict_data = {
        'correct_success': 2,
        'correct_fail': 6,
        'wrong_success': 7,
        'wrong_fail': 15
    }
    strict_total = sum(strict_data.values())
    
    # 创建图表
    fig = plt.figure(figsize=(14, 6))
    
    # 子图1: 热力图（原始场景）
    ax1 = plt.subplot(1, 3, 1)
    matrix_original = np.array([
        [original_data['correct_success'], original_data['correct_fail']],
        [original_data['wrong_success'], original_data['wrong_fail']]
    ])
    im1 = ax1.imshow(matrix_original, cmap='YlOrRd', aspect='auto', vmin=0, vmax=15)
    ax1.set_xticks([0, 1])
    ax1.set_xticklabels(['Success', 'Failure'], fontsize=11)
    ax1.set_yticks([0, 1])
    ax1.set_yticklabels(['Correct', 'Wrong'], fontsize=11)
    ax1.set_title('Original Scenarios (29 episodes)', fontsize=12, fontweight='bold')
    
    # 添加数值标注
    for i in range(2):
        for j in range(2):
            value = matrix_original[i, j]
            percentage = value / original_total * 100
            text = ax1.text(j, i, f'{value}\n({percentage:.1f}%)',
                          ha="center", va="center", color="black", fontsize=10, fontweight='bold')
    
    plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
    
    # 子图2: 热力图（严格场景）
    ax2 = plt.subplot(1, 3, 2)
    matrix_strict = np.array([
        [strict_data['correct_success'], strict_data['correct_fail']],
        [strict_data['wrong_success'], strict_data['wrong_fail']]
    ])
    im2 = ax2.imshow(matrix_strict, cmap='YlOrRd', aspect='auto', vmin=0, vmax=15)
    ax2.set_xticks([0, 1])
    ax2.set_xticklabels(['Success', 'Failure'], fontsize=11)
    ax2.set_yticks([0, 1])
    ax2.set_yticklabels(['Correct', 'Wrong'], fontsize=11)
    ax2.set_title('Strict Scenarios (30 episodes)', fontsize=12, fontweight='bold')
    
    # 添加数值标注
    for i in range(2):
        for j in range(2):
            value = matrix_strict[i, j]
            percentage = value / strict_total * 100
            text = ax2.text(j, i, f'{value}\n({percentage:.1f}%)',
                          ha="center", va="center", color="black", fontsize=10, fontweight='bold')
    
    plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
    
    # 子图3: 分块条形图对比
    ax3 = plt.subplot(1, 3, 3)
    
    categories = ['Correct\n+Success', 'Correct\n+Failure', 'Wrong\n+Success', 'Wrong\n+Failure']
    original_values = [
        original_data['correct_success'] / original_total * 100,
        original_data['correct_fail'] / original_total * 100,
        original_data['wrong_success'] / original_total * 100,
        original_data['wrong_fail'] / original_total * 100
    ]
    strict_values = [
        strict_data['correct_success'] / strict_total * 100,
        strict_data['correct_fail'] / strict_total * 100,
        strict_data['wrong_success'] / strict_total * 100,
        strict_data['wrong_fail'] / strict_total * 100
    ]
    
    x = np.arange(len(categories))
    width = 0.35
    
    bars1 = ax3.bar(x - width/2, original_values, width, label='Original', color='#3498db', alpha=0.8)
    bars2 = ax3.bar(x + width/2, strict_values, width, label='Strict', color='#e74c3c', alpha=0.8)
    
    ax3.set_xlabel('Category', fontsize=11)
    ax3.set_ylabel('Percentage (%)', fontsize=11)
    ax3.set_title('GS × Navigation 2×2 Statistics', fontsize=12, fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels(categories, rotation=0, ha='center', fontsize=10)
    ax3.legend(fontsize=10)
    ax3.grid(axis='y', alpha=0.3, linestyle='--')
    
    # 添加数值标签
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}%',
                    ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'fig6_gs_nav_2x2_analysis.png', dpi=300, bbox_inches='tight')
    plt.savefig(output_dir / 'fig6_gs_nav_2x2_analysis.pdf', bbox_inches='tight')
    print(f"[OK] 图1已保存: {output_dir / 'fig6_gs_nav_2x2_analysis.png'}")
    plt.close()


# ============================================================================
# 图2: "选错+成功"空间距离分布
# ============================================================================

def plot_mismatch_distance_distribution():
    """绘制"选错+成功"空间距离分布"""
    
    # 加载数据
    with open('results/gs_mismatch_distance_analysis.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    distances = [ep['distance'] for ep in data['episode_details']]
    mean_dist = data['mean_distance']
    median_dist = data['median_distance']
    
    # 创建图表
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # 子图1: 直方图
    ax1.hist(distances, bins=10, color='#3498db', alpha=0.7, edgecolor='black', linewidth=1.2)
    ax1.axvline(mean_dist, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_dist:.2f}m')
    ax1.axvline(median_dist, color='green', linestyle='--', linewidth=2, label=f'Median: {median_dist:.2f}m')
    ax1.set_xlabel('Distance (m)', fontsize=11)
    ax1.set_ylabel('Number of Episodes', fontsize=11)
    ax1.set_title('Spatial Distance Distribution\n(Wrong + Success)', fontsize=12, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    
    # 子图2: 条形图（按距离区间）
    bins = [0, 5, 10, 15, 20, 50, 100]
    bin_labels = ['<5m', '5-10m', '10-15m', '15-20m', '20-50m', '≥50m']
    counts = [0] * (len(bins) - 1)
    
    for dist in distances:
        for i in range(len(bins) - 1):
            if bins[i] <= dist < bins[i+1]:
                counts[i] += 1
                break
        if dist >= bins[-1]:
            counts[-1] += 1
    
    colors = ['#2ecc71' if i < 2 else '#f39c12' if i < 4 else '#e74c3c' for i in range(len(counts))]
    bars = ax2.bar(bin_labels, counts, color=colors, alpha=0.7, edgecolor='black', linewidth=1.2)
    ax2.set_xlabel('Distance Range', fontsize=11)
    ax2.set_ylabel('Number of Episodes', fontsize=11)
    ax2.set_title('Spatial Distance Distribution\n(Binned Statistics)', fontsize=12, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    
    # 添加数值标签
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}',
                    ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # 添加统计信息文本框
    stats_text = f'Statistics:\nMean: {mean_dist:.2f}m\nMedian: {median_dist:.2f}m\n<5m: {data["dist_lt_5m"]} episodes\n<20m: {data["dist_lt_20m"]} episodes'
    ax2.text(0.98, 0.98, stats_text, transform=ax2.transAxes,
            fontsize=9, verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig(output_dir / 'fig7_mismatch_distance_distribution.png', dpi=300, bbox_inches='tight')
    plt.savefig(output_dir / 'fig7_mismatch_distance_distribution.pdf', bbox_inches='tight')
    print(f"[OK] 图2已保存: {output_dir / 'fig7_mismatch_distance_distribution.png'}")
    plt.close()


# ============================================================================
# 图3: 干净场景 vs 全体场景对比
# ============================================================================

def plot_clean_vs_all_comparison():
    """绘制干净场景 vs 全体场景对比"""
    
    # 数据
    all_episodes = {
        'total': 29,
        'wrong_success': 7,
        'wrong_success_rate': 24.1
    }
    
    clean_episodes = {
        'total': 18,
        'wrong_success': 2,
        'wrong_success_rate': 11.1
    }
    
    # 创建图表
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # 子图1: 占比对比（条形图）
    categories = ['All Scenarios', 'Clean Scenarios']
    rates = [all_episodes['wrong_success_rate'], clean_episodes['wrong_success_rate']]
    colors = ['#e74c3c', '#2ecc71']
    
    bars = ax1.bar(categories, rates, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5, width=0.6)
    ax1.set_ylabel('Wrong + Success Rate (%)', fontsize=11)
    ax1.set_title('Wrong + Success Rate Comparison', fontsize=12, fontweight='bold')
    ax1.set_ylim(0, max(rates) * 1.3)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    
    # 添加数值标签
    for i, (bar, rate) in enumerate(zip(bars, rates)):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{rate:.1f}%\n({all_episodes["wrong_success"] if i == 0 else clean_episodes["wrong_success"]}/{all_episodes["total"] if i == 0 else clean_episodes["total"]})',
                ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    # 添加下降箭头
    arrow_y = max(rates) * 1.15
    ax1.annotate('', xy=(1, clean_episodes['wrong_success_rate']), 
                xytext=(0, all_episodes['wrong_success_rate']),
                arrowprops=dict(arrowstyle='->', color='red', lw=2))
    ax1.text(0.5, arrow_y, f'Decrease {all_episodes["wrong_success_rate"] - clean_episodes["wrong_success_rate"]:.1f}%',
            ha='center', fontsize=10, color='red', fontweight='bold')
    
    # 子图2: 详细对比（堆叠条形图）
    ax2.barh(['All Scenarios', 'Clean Scenarios'], 
            [all_episodes['wrong_success'], clean_episodes['wrong_success']],
            color='#e74c3c', alpha=0.7, label='Wrong + Success', edgecolor='black', linewidth=1.2)
    ax2.barh(['All Scenarios', 'Clean Scenarios'],
            [all_episodes['total'] - all_episodes['wrong_success'], 
             clean_episodes['total'] - clean_episodes['wrong_success']],
            left=[all_episodes['wrong_success'], clean_episodes['wrong_success']],
            color='#95a5a6', alpha=0.7, label='Others', edgecolor='black', linewidth=1.2)
    
    ax2.set_xlabel('Number of Episodes', fontsize=11)
    ax2.set_title('Episode Count Comparison', fontsize=12, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(axis='x', alpha=0.3, linestyle='--')
    
    # 添加数值标签
    for i, (label, total, wrong_success) in enumerate([
        ('All Scenarios', all_episodes['total'], all_episodes['wrong_success']),
        ('Clean Scenarios', clean_episodes['total'], clean_episodes['wrong_success'])
    ]):
        ax2.text(wrong_success/2, i, f'{wrong_success}',
                ha='center', va='center', fontsize=11, fontweight='bold', color='white')
        ax2.text(wrong_success + (total - wrong_success)/2, i, f'{total - wrong_success}',
                ha='center', va='center', fontsize=11, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_dir / 'fig8_clean_vs_all_comparison.png', dpi=300, bbox_inches='tight')
    plt.savefig(output_dir / 'fig8_clean_vs_all_comparison.pdf', bbox_inches='tight')
    print(f"[OK] 图3已保存: {output_dir / 'fig8_clean_vs_all_comparison.png'}")
    plt.close()


# ============================================================================
# 主函数
# ============================================================================

def main():
    print("="*60)
    print("生成分析类结果可视化图表")
    print("="*60)
    
    # 图1: GS×导航 2×2 统计
    print("\n[1/3] 生成GS×导航2×2统计图表...")
    plot_2x2_heatmap_and_bar()
    
    # 图2: "选错+成功"空间距离分布
    print("\n[2/3] 生成选错+成功空间距离分布图表...")
    plot_mismatch_distance_distribution()
    
    # 图3: 干净场景 vs 全体场景对比
    print("\n[3/3] 生成干净场景vs全体场景对比图表...")
    plot_clean_vs_all_comparison()
    
    print("\n" + "="*60)
    print("[OK] 所有图表生成完成！")
    print(f"输出目录: {output_dir}")
    print("="*60)


if __name__ == '__main__':
    main()

