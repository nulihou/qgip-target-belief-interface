import matplotlib.pyplot as plt
import numpy as np

def create_trajectory_plot():
    # --- 1. Set IEEE Journal Style ---
    # 使用 serif 字体，符合顶刊要求
    plt.rcParams['font.family'] = 'serif'
    plt.rcParams['font.serif'] = ['Times New Roman']
    plt.rcParams['font.size'] = 12
    plt.rcParams['axes.linewidth'] = 1.5
    # 锁定字体嵌入
    plt.rcParams['pdf.fonttype'] = 42
    plt.rcParams['ps.fonttype'] = 42
    
    # --- 2. Construct Simulation Data (Curved Scenario) ---
    t = np.linspace(0, 10, 100)
    x_path = t * 5
    y_path = 4 * np.sin(t / 2)
    
    t_blind_start = 30
    t_blind_end = 50
    
    x_leader = x_path + 5
    y_leader = y_path
    
    x_ours = x_path
    y_ours = y_path
    
    x_base = x_path.copy()
    y_base = y_path.copy()
    
    dx = x_path[t_blind_start] - x_path[t_blind_start-1]
    dy = y_path[t_blind_start] - y_path[t_blind_start-1]
    
    for i in range(t_blind_start, 100):
        x_base[i] = x_base[t_blind_start] + (i - t_blind_start) * dx
        y_base[i] = y_base[t_blind_start] + (i - t_blind_start) * dy
        
    # --- 3. Plotting ---
    fig, ax = plt.subplots(figsize=(8, 4))
    
    # A. Draw Road
    ax.fill_between(x_path, y_path - 3, y_path + 3, color='#eeeeee', label='Road Drivable Area')
    ax.plot(x_path, y_path - 3, color='black', linewidth=2)
    ax.plot(x_path, y_path + 3, color='black', linewidth=2)
    ax.plot(x_path, y_path, color='white', linestyle='--', linewidth=1)
    
    # B. Draw Blackout Zone
    ax.axvspan(x_path[t_blind_start], x_path[t_blind_end], color='#ffe6e6', alpha=1.0, hatch='//')
    
    # FIX: 优化阴影区标注
    # 居中对齐，位于阴影区正上方
    center_x = (x_path[t_blind_start] + x_path[t_blind_end]) / 2
    ax.text(center_x, 8.5, 'Sensor Blackout\n(Ghost Mode Active)', 
            color='#cc0000', fontsize=9, fontweight='bold', ha='center', va='bottom')
    
    # C. Draw Trajectories
    # FIX: 增强 Ground Truth 可见度 (改为虚线，加粗)
    ax.plot(x_leader, y_leader, color='black', linestyle='--', linewidth=1.2, label='Leader (GT)')
    
    # FIX: 增强 Baseline 区分度 (改为深橙色)
    # Baseline 偏离导致 Crash
    crash_idx = 65
    ax.plot(x_base[:crash_idx], y_base[:crash_idx], color='#D35400', linestyle='--', linewidth=2, label='Baseline (No Memory)')
    
    # FIX: 优化 Baseline 崩溃标注
    # 红色叉号
    ax.plot(x_base[crash_idx], y_base[crash_idx], 'x', color='red', markersize=12, markeredgewidth=2, zorder=10)
    # 文字上移，避免接触线条，并加 bbox 避免穿透
    ax.text(x_base[crash_idx] + 2, y_base[crash_idx] - 1.5, 'Deviation / Crash', 
            color='red', fontsize=10, fontweight='bold', ha='center',
            bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=0.5))
    
    # Ours
    ax.plot(x_ours, y_ours, color='#2ca02c', linestyle='-', linewidth=3, label='QGIP-Net (Ours)')
    
    # --- 4. Styling ---
    ax.set_xlabel('Longitudinal Position (m)', fontsize=12)
    ax.set_ylabel('Lateral Position (m)', fontsize=12)
    # FIX: 确保等比例，避免弯道失真
    ax.set_aspect('equal')
    ax.set_xlim(0, 50)
    ax.set_ylim(-8, 12) # 增加 Y 轴上限，容纳顶部文字
    
    # FIX: 调整图例位置，防止遮挡
    # 使用 bbox_to_anchor 将图例移到绘图区侧面（如果允许），或者保持左上角但更紧凑
    # 这里保持左上角，因为图比较宽，左上角通常是空的
    ax.legend(loc='upper left', framealpha=0.9, fontsize=10, frameon=True, edgecolor='gray')
    
    plt.tight_layout()
    
    # --- 5. Save ---
    output_dir = 'd:/project/lc_org_v2.0/paper_figures/'
    # 使用 bbox_inches='tight', pad_inches=0.05
    plt.savefig(output_dir + 'figure6_trajectory.pdf', format='pdf', dpi=300, bbox_inches='tight', pad_inches=0.05)
    plt.savefig(output_dir + 'figure6_trajectory.png', format='png', dpi=300, bbox_inches='tight', pad_inches=0.05)
    plt.close()

if __name__ == "__main__":
    create_trajectory_plot()
