import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.patheffects as path_effects
import numpy as np

# --- RAL/IEEE Top-Tier Style Configuration ---
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman']
plt.rcParams['mathtext.fontset'] = 'stix'
plt.rcParams['font.size'] = 11
plt.rcParams['axes.linewidth'] = 1.0
plt.rcParams['xtick.direction'] = 'in'
plt.rcParams['ytick.direction'] = 'in'
# 锁定字体嵌入
plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['ps.fonttype'] = 42

# Colors
C_OURS = '#D62728' # Brick Red
C_BASE = '#7F7F7F' # Grey
C_SOTA = '#1F77B4' # Blue
C_ZONE = '#F0F9E8' # Very light green (almost white)

def create_efficiency_plot_ral():
    # Data
    methods = [
        ("TransFuser", 55, 76, 'triangle', C_SOTA),    
        ("CILRS", 15, 52, 'square', C_BASE),          
        ("Rule-Based", 2, 0.5, 'x', C_BASE),             
        ("GAT", 18, 65, 'circle', C_BASE),       
        ("QGIP-Net (Ours)", 38, 76, 'star', C_OURS)       
    ]
    
    fig, ax = plt.subplots(figsize=(6, 5))
    
    # 1. Target Zone (Subtle)
    # RAL prefers subtle indications over loud colored regions
    # Expanded to 40ms (25Hz)
    rect = patches.Rectangle((0, 60), 40, 45, linewidth=0, edgecolor='none', facecolor=C_ZONE, zorder=0)
    ax.add_patch(rect)
    ax.text(2, 102, "Real-time & Robust Region", fontsize=9, fontstyle='italic', color='#4CA64C', zorder=1)

    # 2. 25Hz Limit
    ax.axvline(40, color='black', linestyle=':', linewidth=1.0, zorder=1)
    ax.text(40.5, 6, "25Hz Latency Limit (40ms)", fontsize=9, rotation=90, va='bottom', color='#333333', fontweight='bold', alpha=0.7)

    # 3. Plot Points
    for name, lat, succ, shape, color in methods:
        # Markers
        if shape == 'star':
            marker = '*'
            s = 350 # 稍微加大
            # 优化五角星边缘：将 linewidth 设为 0.8，让它更精致
            edge = 'black'
            lw = 0.8
            zorder = 10
            # 特殊处理：添加外发光/阴影效果
            ax.scatter(lat, succ, c=color, marker=marker, s=s, edgecolors=edge, linewidth=lw, zorder=zorder,
                       path_effects=[path_effects.SimpleLineShadow(offset=(2, -2), alpha=0.3), path_effects.Normal()])
        elif shape == 'triangle':
            marker = '^'
            s = 100
            edge = 'black'
            lw = 1.0
            zorder = 5
            ax.scatter(lat, succ, c=color, marker=marker, s=s, edgecolors=edge, linewidth=lw, zorder=zorder)
        elif shape == 'square':
            marker = 's'
            s = 80
            edge = 'black'
            lw = 1.0
            zorder = 5
            ax.scatter(lat, succ, c=color, marker=marker, s=s, edgecolors=edge, linewidth=lw, zorder=zorder)
        elif shape == 'circle':
            marker = 'o'
            s = 100
            edge = 'black'
            lw = 1.0
            zorder = 5
            ax.scatter(lat, succ, c=color, marker=marker, s=s, edgecolors=edge, linewidth=lw, zorder=zorder)
        else: # x
            marker = 'x'
            s = 80
            edge = color
            lw = 1.5
            zorder = 5
            ax.scatter(lat, succ, c=color, marker=marker, s=s, edgecolors=edge, linewidth=lw, zorder=zorder)
        
        # Labels
        offset_y = 4
        if "Rule" in name:
            # 向右偏移 Rule-Based 标签
            ax.text(lat + 4, succ, name, va='center', fontsize=9)
        elif "Ours" in name:
            ax.text(lat, succ + 5, r"$\bf{QGIP}$-$\bf{Net}$" + "\n(Ours)", 
                   ha='center', va='bottom', fontsize=10, color=C_OURS, fontweight='bold')
        elif "TransFuser" in name:
            ax.text(lat, succ - 8, name, ha='center', va='top', fontsize=9)
        elif "CILRS" in name:
            ax.text(lat, succ - 5, name, ha='center', va='top', fontsize=9)
        elif "GAT" in name:
            ax.text(lat, succ - 5, name, ha='center', va='top', fontsize=9)

    # 4. Pareto Connection (Ours vs SOTA)
    # 加粗虚线
    ax.plot([38, 55], [76, 76], color='grey', linestyle='--', linewidth=1.5, zorder=5)
    # 给文字加白色背景 bbox
    ax.text(46.5, 78, "Matching Accuracy", ha='center', va='bottom', fontsize=9, color='grey', style='italic',
            bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1))

    # 5. Axes
    ax.set_xlabel("Inference Latency (ms)", fontsize=11)
    ax.set_ylabel("Success Rate under Occlusion (%)", fontsize=11)
    ax.set_xlim(-2, 70)
    # 增加 Y 轴上限，留出呼吸空间
    ax.set_ylim(-2, 110)
    
    # Grid
    # 调低网格线透明度，让绿色区域更干净
    ax.grid(True, linestyle='-', color='#E0E0E0', linewidth=0.5, alpha=0.5, zorder=0)
    
    # Spines
    for spine in ax.spines.values():
        spine.set_linewidth(1.0)
        spine.set_color('black')

    plt.tight_layout()
    output_dir = './'
    plt.savefig(output_dir + 'figure5_efficiency.pdf', bbox_inches='tight', pad_inches=0.05)
    plt.savefig(output_dir + 'figure5_efficiency.png', dpi=300, bbox_inches='tight', pad_inches=0.05)

if __name__ == "__main__":
    create_efficiency_plot_ral()
