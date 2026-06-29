import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.gridspec import GridSpec
import numpy as np

# --- RAL/IEEE Top-Tier Style Configuration ---
# RAL requires high contrast, readable in grayscale, serif fonts
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman']
plt.rcParams['mathtext.fontset'] = 'stix' # Better math rendering
plt.rcParams['font.size'] = 10
plt.rcParams['axes.linewidth'] = 1.0
plt.rcParams['axes.labelsize'] = 10
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
# 锁定字体嵌入
plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['ps.fonttype'] = 42

# Color Palette (Colorblind friendly + Academic)
COLORS = {
    'obs': '#005293',      # IEEE Blue (Deep)
    'obs_fill': '#A2C4E6', # Light Blue
    'pred': '#D45000',     # Safety Orange (High contrast vs Blue)
    'pred_fill': '#FAD7C3',# Light Orange
    'gt': '#333333',       # Dark Grey
    'road': '#F0F0F0',     # Very light grey
    'lane': '#888888',     # Medium grey
    'grid': '#E0E0E0',     # Light grid
    'text': '#000000'
}

def draw_vehicle_schematic(ax, x, y, heading=0, color='blue', alpha=1.0, 
                         mode='solid', label=None, with_uncertainty=False, label_offset=(0, -0.8)):
    """
    Draws a technical schematic of a vehicle.
    mode: 'solid' (Observation), 'ghost' (Prediction), 'gt' (Ground Truth)
    """
    w, h = 1.8, 3.8 # meters (approx scale)
    
    # Transform for heading
    t = np.radians(heading)
    c, s = np.cos(t), np.sin(t)
    R = np.array([[c, -s], [s, c]])
    
    # Vehicle corners (centered at 0,0)
    corners = np.array([
        [-w/2, -h/2], [w/2, -h/2], [w/2, h/2], [-w/2, h/2]
    ])
    
    # Rotate and translate
    corners_trans = np.dot(corners, R.T) + np.array([x, y])
    
    # Styles
    if mode == 'solid':
        fc = COLORS['obs_fill']
        ec = COLORS['obs']
        ls = '-'
        lw = 1.5
        zorder = 10
    elif mode == 'ghost':
        fc = 'none' # Transparent fill for schematic look
        ec = COLORS['pred']
        ls = '--' # Dashed for prediction
        lw = 1.5
        zorder = 9
    elif mode == 'gt':
        fc = 'none'
        ec = COLORS['gt']
        ls = ':'
        lw = 1.0
        zorder = 8

    # Draw Chassis
    poly = patches.Polygon(corners_trans, closed=True, fc=fc, ec=ec, lw=lw, ls=ls, alpha=alpha, zorder=zorder)
    ax.add_patch(poly)
    
    # Draw Heading Arrow (Vector)
    arrow_len = 2.5
    ax.arrow(x, y, arrow_len*s, arrow_len*c, head_width=0.6, head_length=0.8, 
             fc=ec, ec=ec, alpha=alpha, zorder=zorder+1)
    
    # Draw Center of Mass
    ax.plot(x, y, 'o', color=ec, markersize=4, zorder=zorder+1)

    # Uncertainty Ellipse (Covariance)
    if with_uncertainty:
        # Drawing a schematic 2-sigma ellipse
        # In a real scenario, this comes from the Kalman Filter P matrix
        # Here we simulate a realistic covariance shape aligned with heading
        ell_w = w * 1.8
        ell_h = h * 1.4
        ellipse = patches.Ellipse((x, y), width=ell_w, height=ell_h, angle=heading,
                                fc=COLORS['pred'], alpha=0.15, ec=COLORS['pred'], ls=':', lw=1.0, zorder=zorder-1)
        ax.add_patch(ellipse)

    # Label - Optimized with bbox and zorder
    if label:
        # Add offset to label position to avoid overlapping with vehicle
        ax.text(x + label_offset[0], y - h/2 + label_offset[1], label, ha='center', va='top', fontsize=9, color=COLORS['text'],
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=0.5), zorder=100)

def setup_engineering_axis(ax, title, show_ylabel=False):
    ax.set_aspect('equal')
    ax.set_xlim(-4, 4)
    # Increased ylim to prevent title overlap
    ax.set_ylim(-2, 22) 
    
    # Engineering Grid
    ax.grid(True, which='major', linestyle='-', color=COLORS['grid'], linewidth=0.5)
    ax.set_xticks(np.arange(-4, 5, 2))
    ax.set_yticks(np.arange(0, 23, 5))
    ax.set_xlabel("Lateral Position (m)")
    
    if show_ylabel:
        ax.set_ylabel("Longitudinal Position (m)")
    else:
        ax.set_yticklabels([])
    
    ax.set_title(title, fontsize=11, fontweight='bold', pad=12)
    
    # Draw Road Boundaries
    ax.axvline(-3.5, color='black', lw=1.5) # Left curb
    ax.axvline(3.5, color='black', lw=1.5)  # Right curb
    # Lane divider
    ax.plot([0, 0], [-2, 22], color=COLORS['lane'], linestyle='--', lw=1.0, dashes=(5, 5))

def create_ghost_viz_ral():
    fig = plt.figure(figsize=(10, 5.5), dpi=300) # Increased height slightly
    gs = GridSpec(1, 3, figure=fig, wspace=0.1)
    
    # --- Scenario Data ---
    # T1: Normal
    # T2: Occluded
    # T3: Recovered
    
    # Subplot 1: T_k (Observation)
    ax1 = fig.add_subplot(gs[0])
    setup_engineering_axis(ax1, r"(a) Active Tracking ($t_k$)", show_ylabel=True)
    
    # Trajectory History
    ax1.plot([0, 0], [0, 4], color=COLORS['obs'], lw=1.0, linestyle='-')
    ax1.plot(0, 0, 'x', color=COLORS['obs'], markersize=4) # Past point
    
    # Vehicle
    draw_vehicle_schematic(ax1, 0, 4, heading=5, mode='solid', label=r"$\mathbf{z}_k$ (Obs)")
    
    # Annotation
    ax1.text(-2.5, 17, "Sensor: ON", color=COLORS['obs'], fontweight='bold', fontsize=9,
             bbox=dict(facecolor='white', edgecolor=COLORS['obs'], boxstyle='round,pad=0.3', alpha=0.9), zorder=100)

    # Subplot 2: T_k+1 (Occlusion / Ghost)
    ax2 = fig.add_subplot(gs[1])
    setup_engineering_axis(ax2, r"(b) Ghost Prediction ($t_{k+1}$)")
    
    # Occlusion Zone
    # Draw a shaded polygon representing sensor blind spot
    # 1. 减小阴影密度 (将 '///' 改为 '/')，避免干扰文字
    blind_poly = patches.Rectangle((-4, 6), 8, 14, fc='#eeeeee', hatch='\\\\', lw=0.5, alpha=0.3, zorder=0)
    ax2.add_patch(blind_poly)
    ax2.text(0, 16.5, "OCCLUSION ZONE", ha='center', fontsize=9, 
             color='#555555', fontweight='bold', alpha=0.9, 
             bbox=dict(facecolor='white', edgecolor='#dddddd', boxstyle='round,pad=0.2'), zorder=100)
    
    # 2. 调整 Ground Truth 标签：移到车辆上方
    draw_vehicle_schematic(ax2, 0.5, 9, heading=5, mode='gt', alpha=0.4)
    # ax2.text(0.5, 10.5, "Ground Truth", ha='center', va='bottom', fontsize=8, color='#666666',
    #          bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=0.2), zorder=101)
    ax2.annotate("Ground Truth", xy=(0.8, 12.0), xytext=(2.0, 14.0), 
              arrowprops=dict(arrowstyle="->", color=COLORS['gt'], lw=0.8), 
              ha='left', fontsize=9, color=COLORS['gt'], 
              bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=0.2))
    
    # 3. 调整 Ghost 预测标签：移到车辆下方，并增加 y 轴偏移
    draw_vehicle_schematic(ax2, 0.2, 8.8, heading=5, mode='ghost', with_uncertainty=True)
    # 使用 LaTeX 格式，并增加较大的向下偏移 (offset)
    # 稍微偏移 Ghost 标签，避开中心虚线，并添加极小的白色背景以防万一
    # 字体使用粗体数学斜体 (mathbf + mathit 模拟，或直接 bm)
    ax2.text(0.8, 5.0, r"$\hat{\mathbf{x}}_{k+1|k}$ (Ghost)", 
          ha='left', va='top', fontsize=9, color=COLORS['pred'], 
          bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=0.1), zorder=101)
    
    # 4. 优化 3-sigma 标签：移到椭圆边缘的右下角
    # 将 3-sigma 移到右下角更清爽的区域
    ax2.text(2.8, 6.8, r"$3\sigma$", color=COLORS['pred'], 
             fontsize=8, fontweight='bold', fontstyle='italic', zorder=101)
    
    # Annotation
    ax2.text(2, 2, "Kalman Propagate", fontsize=8, color=COLORS['pred'], ha='center',
             bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=0.5), zorder=100)

    # Subplot 3: T_k+2 (Recovery)
    ax3 = fig.add_subplot(gs[2])
    setup_engineering_axis(ax3, r"(c) Re-Association ($t_{k+2}$)")
    
    # Observation returns
    # label_offset=(0.3, -0.8) slightly move label to right to avoid overlap with trajectory line
    draw_vehicle_schematic(ax3, 1.2, 14, heading=2, mode='solid')
    # 将 z_{k+2} 标签稍微远离车尾，增加呼吸感，并进一步偏移以避开车辆边缘
    ax3.text(1.4, 11.5, r"$\mathbf{z}_{k+2}$ (Obs)", ha='center', va='top', 
          fontsize=9, color=COLORS['text'], zorder=101)
    
    # Ghost Prediction continues (for matching)
    draw_vehicle_schematic(ax3, 0.6, 13.8, heading=5, mode='ghost', alpha=0.6)
    
    # Matching Link
    ax3.annotate("", xy=(1.2, 14), xytext=(0.6, 13.8),
                arrowprops=dict(arrowstyle="<->", color='black', lw=1.0), zorder=99)
    # Offset text slightly to avoid overlapping arrow
    # IoU Match 标签稍微靠右，避免离车太近
    ax3.text(3.2, 12.5, r"IoU Match $> \tau$", fontsize=8, ha='center', 
          bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=0.1), zorder=100)
    
    # Trajectory alignment
    # Plot the corrected trajectory
    ax3.plot([0, 0.2, 1.2], [4, 8.8, 14], color=COLORS['obs'], linestyle='-', lw=1.5, alpha=0.5)

    plt.tight_layout()
    plt.savefig('figure3_ghost_tracking.pdf', bbox_inches='tight', pad_inches=0.05)
    plt.savefig('figure3_ghost_tracking.png', dpi=300, bbox_inches='tight', pad_inches=0.05)

if __name__ == "__main__":
    create_ghost_viz_ral()
