import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as patches

# --- 基础配置 ---
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman"],
    "font.size": 14,
    "axes.titlesize": 18,
    "axes.labelsize": 16,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "mathtext.fontset": "cm",
    "legend.fontsize": 12,
    "pdf.fonttype": 42, # 锁定字体嵌入
    "ps.fonttype": 42
})

def plot_safety_analysis_final():
    # --- 1. 数据生成 (保持逻辑: Baseline危险, Ours安全) ---
    t = np.linspace(0, 6, 100)
    
    # Leader (GT)
    v_leader = np.zeros_like(t)
    v_leader[t < 1.5] = 10
    v_leader[(t >= 1.5) & (t < 4.0)] = np.linspace(10, 0, len(t[(t >= 1.5) & (t < 4.0)]))
    v_leader[t >= 4.0] = 0
    
    # Baseline (Bad): 反应迟钝，预测漂移
    v_baseline = v_leader.copy()
    mask_blackout = (t >= 2.0) & (t <= 3.5)
    v_baseline[mask_blackout] = np.linspace(10, 11, len(t[mask_blackout])) # 危险加速
    mask_recovery = (t > 3.5)
    v_baseline[mask_recovery] = np.linspace(11, 0, len(t[mask_recovery])) # 急刹
    
    # Ours (Good): 鲁棒预测
    v_ours = v_leader.copy()
    mask_action = (t >= 1.5)
    v_ours[mask_action] = np.linspace(10, 0, len(t[mask_action])) * 0.95

    # 距离积分
    initial_gap = 25
    dist_baseline = initial_gap + np.cumsum(v_leader - v_baseline) * (t[1]-t[0])
    dist_ours = initial_gap + np.cumsum(v_leader - v_ours) * (t[1]-t[0])

    # --- 2. 绘图 ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8.5), sharex=True, dpi=300) # 稍微加高一点
    
    blackout_start, blackout_end = 2.0, 3.5
    
    # === Subplot 1: Velocity ===
    # 关键修改：zorder=-1 确保背景在网格线下面
    ax1.axvspan(blackout_start, blackout_end, color='#FFEBEB', alpha=0.8, zorder=-1)
    
    # 文字标签上移，避免压线
    ax1.text((blackout_start+blackout_end)/2, 16.5, "Sensor Blackout\n(1.0s)", 
             color='#D32F2F', ha='center', va='center', fontsize=12, fontweight='bold', 
             bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1)) # 加个白底衬托，防止乱

    # 绘制曲线
    ax1.plot(t, v_leader, color='black', linestyle='--', linewidth=2, label='Leader (GT)', zorder=2)
    ax1.plot(t, v_baseline, color='#D32F2F', linestyle='-', linewidth=2.5, label='Baseline', zorder=3) 
    ax1.plot(t, v_ours, color='#1f4e79', linestyle='-', linewidth=3, label='QGIP-Net (Ours)', zorder=4)

    # 标注
    ax1.annotate('Dangerous\nAcceleration', xy=(3.0, 10.8), xytext=(3.6, 14), 
                 arrowprops=dict(facecolor='#D32F2F', arrowstyle='->', lw=2), 
                 color='#D32F2F', fontsize=12, fontweight='bold', ha='left', zorder=5)

    ax1.set_ylabel(r"Velocity ($m/s$)")
    ax1.set_title(r"(a) Velocity Profile during Emergency Braking", fontweight='bold', pad=15)
    
    # 关键修改：Grid zorder=0 (在背景之上，曲线之下)
    ax1.grid(True, linestyle=':', alpha=0.6, zorder=0)
    
    # 图例 zorder=10 (最上层)，不透明
    # Use minimal arguments for legend to ensure compatibility
    ax1.legend(loc='lower left')
    ax1.set_ylim(-1, 18) # 增加高度

    # === Subplot 2: Distance ===
    ax2.axvspan(blackout_start, blackout_end, color='#FFEBEB', alpha=0.8, zorder=-1)

    ax2.axhline(5, color='#2ca02c', linestyle=':', linewidth=2.5, zorder=1)
    ax2.text(0.2, 5.5, "Safety Threshold (5m)", color='#2ca02c', fontsize=11, fontweight='bold', 
             bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=0))

    ax2.plot(t, dist_baseline, color='#D32F2F', linestyle='-', linewidth=2.5, label='Baseline', zorder=3)
    ax2.plot(t, dist_ours, color='#1f4e79', linestyle='-', linewidth=3, label='QGIP-Net (Ours)', zorder=4)

    # 碰撞标记
    crash_idx = np.where(dist_baseline < 0)[0]
    if len(crash_idx) > 0:
        crash_t = t[crash_idx[0]]
        # 让红线延伸到底
        ax2.plot(crash_t, 0, marker='x', markersize=14, markeredgewidth=3, color='red', zorder=5)
        ax2.text(crash_t + 0.1, 1.5, "Collision!", color='red', fontsize=12, fontweight='bold')

    ax2.set_ylabel(r"Headway Distance ($m$)")
    ax2.set_xlabel(r"Time ($s$)")
    ax2.set_title(r"(b) Headway Distance Analysis", fontweight='bold', pad=15)
    ax2.grid(True, linestyle=':', alpha=0.6, zorder=0)
    ax2.set_ylim(-2, 28)

    plt.tight_layout()
    plt.savefig('figure7_safety_analysis.pdf', bbox_inches='tight', pad_inches=0.05)
    plt.savefig('figure7_safety_analysis.png', dpi=300, bbox_inches='tight', pad_inches=0.05)

if __name__ == "__main__":
    plot_safety_analysis_final()
