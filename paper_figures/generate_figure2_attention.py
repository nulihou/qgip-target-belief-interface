import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import numpy as np

# 1. 基础设置：字体与风格
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman"], # 顶刊标配字体
    "font.size": 12,
    "axes.titlesize": 18,
    "axes.labelsize": 14,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "mathtext.fontset": "cm", # 数学公式使用LaTeX风格
    "pdf.fonttype": 42, # 锁定字体嵌入
    "ps.fonttype": 42
})

def draw_road_background_corrected(ax, x_min, x_max, y_min, y_max):
    """
    修正后的路面背景：
    1. 确保画板够宽，不会切掉车。
    2. 车道线画在车辆之间，而不是车底下。
    """
    # 绘制灰色沥青背景
    ax.add_patch(patches.Rectangle((x_min, y_min), x_max-x_min, y_max-y_min, 
                                   color='#F0F2F5', zorder=0)) 
    
    # 车道线逻辑修正：
    # 假设车在 x=0, 4, 8, 12 的位置，那么车道分隔线应该在 -2, 2, 6, 10, 14
    lane_lines = [-2, 2, 6, 10, 14]
    
    # 绘制白色虚线 (中间的分隔线)
    # 我们保留最左(-2)和最右(14)作为实线边界，中间作为虚线
    for x in lane_lines[1:-1]: # 2, 6, 10
        ax.plot([x, x], [y_min, y_max], color='white', linestyle='--', 
                linewidth=2, dashes=(10, 10), zorder=1)

    # 绘制路边实线 (Road Boarders) - 加强路界感
    ax.plot([lane_lines[0], lane_lines[0]], [y_min, y_max], color='#B0B3B8', linewidth=3, zorder=1) # 左边界 -2
    ax.plot([lane_lines[-1], lane_lines[-1]], [y_min, y_max], color='#B0B3B8', linewidth=3, zorder=1) # 右边界 14

def draw_vehicle_refined(ax, x, y, width=1.8, height=3.8, color='white', 
                         edgecolor='none', label=None, is_ego=False, weight=0):
    """更精致的车辆绘制"""
    z_order = 10
    
    # 阴影效果 (Shadow) - 让车“浮”在路面上
    shadow = patches.FancyBboxPatch(
        (x - width/2 + 0.2, y - height/2 - 0.2), width, height,
        boxstyle="round,pad=0.1,rounding_size=0.4",
        facecolor='black', alpha=0.1, zorder=z_order-1
    )
    ax.add_patch(shadow)

    # 车辆主体
    box = patches.FancyBboxPatch(
        (x - width/2, y - height/2), width, height,
        boxstyle="round,pad=0.1,rounding_size=0.4",
        linewidth=1.5, edgecolor=edgecolor, facecolor=color, zorder=z_order
    )
    ax.add_patch(box)

    # 标签处理
    if label:
        if is_ego:
            # Ego车辆文字
            ax.text(x, y, "Ego", ha='center', va='center', 
                    fontsize=12, color='white', fontweight='bold', zorder=z_order+2)
            # Ego特殊的辉光边框
            glow = patches.FancyBboxPatch(
                (x - width/2, y - height/2), width, height,
                boxstyle="round,pad=0.2,rounding_size=0.5",
                linewidth=0, facecolor='#1f4e79', alpha=0.15, zorder=z_order-2
            )
            ax.add_patch(glow)
        else:
            # 其他车辆显示权重
            txt_col = 'black' if weight < 0.6 else 'white' # 智能变色
            ax.text(x, y, f"{weight:.2f}", ha='center', va='center', 
                    fontsize=11, color=txt_col, fontweight='bold', zorder=z_order+2)
            
    # 添加一个小三角表示车头方向，放在车辆前方外面，不干扰文字
    ax.plot(x, y + height/2 + 1.2, marker='^', markersize=6, color=edgecolor or '#555', clip_on=False, zorder=z_order)


def plot_scenario_final(ax, title, ego_pos, neighbors, weights):
    ax.set_title(title, pad=15, fontweight='bold')
    
    # --- 关键修正点：视野范围 ---
    # 之前的 x_max=12 切掉了位于 x=12 的车。
    # 现在我们将 x_max 设为 16，并把 x_min 设为 -4，保证所有车都在画面中央且完整。
    x_min, x_max = -4, 16
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(-5, 35)
    ax.set_aspect('equal')
    ax.axis('off')

    # 绘制背景
    draw_road_background_corrected(ax, x_min, x_max, -5, 35)

    # 自定义Colorbar: 使用 OrRd (Orange-Red)
    # 关键：设置vmin > 0 以避免极低权重变成白色看不见
    cmap = plt.get_cmap('OrRd')
    norm = mcolors.Normalize(vmin=0, vmax=1.0)

    # 先画连线 (Attention Links)
    for (nx, ny), w in zip(neighbors, weights):
        # 线的颜色
        line_color = cmap(norm(w))
        # 线的透明度：权重极小时稍微透明，但不完全消失
        line_alpha = 0.4 + 0.6 * w
        # 线宽
        line_width = 1 + w * 6
        
        ax.plot([ego_pos[0], nx], [ego_pos[1], ny], 
                color=line_color, linewidth=line_width, alpha=line_alpha, 
                zorder=5, solid_capstyle='round')

    # 画邻居车
    for (nx, ny), w in zip(neighbors, weights):
        # 填充色：基于权重
        fill_color = cmap(norm(w))
        # 边框色：稍微深一点
        edge_color = cmap(norm(w + 0.2))
        
        draw_vehicle_refined(ax, nx, ny, color=fill_color, edgecolor=edge_color, 
                             label=str(w), weight=w, is_ego=False)

    # 最后画Ego (确保在最上层)
    # 使用深海军蓝
    draw_vehicle_refined(ax, ego_pos[0], ego_pos[1], color='#2C3E50', edgecolor='#1A252F', 
                         label='Ego', is_ego=True)

    return cmap, norm

def create_figure2_attention():
    # --- 主程序 ---
    # 关键修改：figsize 从 (15, 9) 改为 (12, 12)，让画布更接近正方形，减少中间留白
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 12), dpi=300, facecolor='white') 
    
    # 场景数据
    ego_pos_1 = (4, 0)
    neighbors_1 = [(4, 15), (4, 25), (0, 7), (8, 0)]
    weights_1 = [0.95, 0.10, 0.05, 0.02]
    
    ego_pos_2 = (8, 0)
    neighbors_2 = [(4, 7), (8, 15), (8, 25), (12, 0)]
    weights_2 = [0.85, 0.30, 0.05, 0.01]
    
    # 绘图
    cmap, norm = plot_scenario_final(ax1, r"(a) $\mathbf{Q}$: Follow Leader Mode", ego_pos_1, neighbors_1, weights_1)
    plot_scenario_final(ax2, r"(b) $\mathbf{Q}$: Lane Change Left Mode", ego_pos_2, neighbors_2, weights_2)
    
    # 添加 Colorbar
    # 调整位置，使其居中且不拥挤
    cax = fig.add_axes([0.3, 0.08, 0.4, 0.02])
    cb = fig.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation='horizontal')
    cb.set_label(r'Attention Weight $\mathcal{A}$', fontsize=14, labelpad=8)
    cb.outline.set_visible(False) # 去掉Colorbar的黑框，更现代
    cb.ax.tick_params(size=0) # 去掉刻度线
    
    # 关键：将 wspace 设为 0.02，因为figsize变窄了，现在两图会自然紧挨着
    plt.subplots_adjust(left=0.02, right=0.98, bottom=0.12, top=0.92, wspace=0.02)
    
    plt.savefig('figure2_attention.pdf', bbox_inches='tight', pad_inches=0.05)
    plt.savefig('figure2_attention.png', dpi=300, bbox_inches='tight', pad_inches=0.05)

if __name__ == "__main__":
    create_figure2_attention()
