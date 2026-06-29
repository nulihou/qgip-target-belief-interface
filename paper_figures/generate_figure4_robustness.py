import matplotlib.pyplot as plt
import numpy as np

def create_robustness_plot():
    # --- 1. Set IEEE Journal Style ---
    # 使用 serif 字体配合 bold weight，更符合 IEEE 顶刊风格
    plt.rcParams['font.family'] = 'serif'
    plt.rcParams['font.weight'] = 'bold'
    plt.rcParams['font.size'] = 12
    # 调整坐标轴粗细
    plt.rcParams['axes.linewidth'] = 1.2
    plt.rcParams['xtick.major.width'] = 1.2
    plt.rcParams['ytick.major.width'] = 1.2
    plt.rcParams['grid.alpha'] = 0.3
    # 确保刻度标签也是粗体
    plt.rcParams['axes.labelweight'] = 'bold'
    # 锁定字体嵌入
    plt.rcParams['pdf.fonttype'] = 42
    plt.rcParams['ps.fonttype'] = 42
    
    # --- 2. Data Preparation ---
    x = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    y_rule = np.array([95, 0,  0,  0,  0])
    # Updated with N=300 (1.0s) and N=100 (1.5/2.0s) data
    # NoKF: 1.0s=75.7%, 1.5s=72.0%, 2.0s=76.0%
    y_ablation = np.array([96, 85, 75.7, 72.0, 76.0])
    # Ours: 1.0s=76.0%, 1.5s=80.0%, 2.0s=84.0%
    y_ours = np.array([100, 92, 76.0, 80.0, 84.0])
    
    # --- 3. Plotting ---
    fig, ax = plt.subplots(figsize=(6, 4.5))
    
    # Draw Lines
    ax.plot(x, y_rule, marker='x', markersize=8, linestyle='--', color='gray', 
            linewidth=2, label='Baseline-Rule', zorder=10)
    ax.plot(x, y_ablation, marker='s', markersize=7, linestyle='-.', color='#3b75af', 
            linewidth=2, label='Ablation (No KF)', zorder=10)
    ax.plot(x, y_ours, marker='o', markersize=8, linestyle='-', color='#d62728', 
            linewidth=2.5, label='QGIP-Net (Ours)', zorder=10)
    
    # --- 4. Styling & Annotations ---
    ax.set_xlabel('Duration of Sensor Blackout (s)', fontsize=12)
    ax.set_ylabel('Success Rate (%)', fontsize=12)
    
    # 加粗刻度标签
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontweight('bold')
        
    ax.grid(True, linestyle='--', which='both')
    
    ax.set_ylim(-5, 115) 
    ax.set_xlim(-0.1, 2.1)
    
    # FIX: 调整图例位置到右上角
    # loc='upper right'
    ax.legend(frameon=True, fontsize=10, loc='lower left', framealpha=0.9, edgecolor='gray')
    
    # FIX: 修改标注箭头为双向，直观展示 Gap
    # 从 Ours (y=80) 指向 Ablation (y=72) at x=1.5
    ax.annotate('', xy=(1.5, 80), xytext=(1.5, 72), 
                arrowprops=dict(arrowstyle='<->', color='black', lw=1.5), zorder=15)
    
    # 文字放在箭头旁边，略微偏移
    ax.text(1.55, 76, "+8% Gap", fontweight='bold', fontsize=11, rotation=0, va='center', zorder=15)
    
    # 辅助虚线
    # 确保这条虚线的 zorder 较低，不要遮挡住数据点
    ax.vlines(x=1.0, ymin=0, ymax=72, colors='red', linestyles='dotted', alpha=0.5, zorder=5)
    
    # --- 5. Save ---
    plt.tight_layout()
    output_dir = './' # 保存到当前目录，即 d:/project/lc_org_v2.0/paper_figures/
    plt.savefig(output_dir + 'figure4_robustness.pdf', format='pdf', dpi=300, bbox_inches='tight', pad_inches=0.05)
    plt.savefig(output_dir + 'figure4_robustness.png', format='png', dpi=300, bbox_inches='tight', pad_inches=0.05)
    plt.close()

if __name__ == "__main__":
    create_robustness_plot()
