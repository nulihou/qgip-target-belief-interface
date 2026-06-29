import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as patches
import os

# IEEE 字体设置
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman']
plt.rcParams['font.size'] = 11

def draw_lattice_schematic():
    fig, ax = plt.subplots(figsize=(8, 4)) # 宽长比调整为 2:1 适应横向布局

    # 1. 绘制车道背景 (Road Context)
    ax.plot([0, 55], [3.5, 3.5], 'k-', linewidth=2, alpha=0.3) # 左边界
    ax.plot([0, 55], [-3.5, -3.5], 'k-', linewidth=2, alpha=0.3) # 右边界
    ax.plot([0, 55], [0, 0], 'k--', linewidth=1.5, alpha=0.3, label='Lane Center') # 中心线

    # 2. 模拟 Lattice 采样轨迹 (使用多项式模拟)
    x = np.linspace(0, 50, 100)
    
    # 备选轨迹 (Candidate Paths) - 模拟采样 d = -3, 0, 3
    offsets = [-3, -1.5, 0, 1.5, 3]
    for d_end in offsets:
        # 简单的三次多项式模拟: y = a*x^3 + b*x^2
        # 这是一个视觉近似，实际 Lattice 是五次多项式
        # y(0)=0, y'(0)=0, y(50)=d_end, y'(50)=0
        # Let x_n = x/50. y = d_end * (3*x_n^2 - 2*x_n^3) (Smoothstep)
        x_n = x / 50.0
        y_cand = d_end * (3 * x_n**2 - 2 * x_n**3)
        
        # 遇到障碍物的轨迹画成半透明
        if 1.0 < d_end < 3.5:
            style = {'color': 'red', 'alpha': 0.15, 'linewidth': 1} # 碰撞轨迹
        else:
            style = {'color': '#9467bd', 'alpha': 0.3, 'linewidth': 1} # 可行轨迹
            
        ax.plot(x, y_cand, **style)

    # 手动添加图例用的“虚假”线条
    ax.plot([], [], color='#9467bd', alpha=0.5, label='Candidate Trajectories')
    ax.plot([], [], color='red', alpha=0.3, label='Discarded (Collision)')

    # 3. 绘制最优轨迹 (Optimal) - 假设是一个换道避让动作
    # y_opt = 2.0 * (x/50)**2 * (3 - 2*(x/50)) # 稍微避让
    # 使用中心稍微偏左的轨迹作为最优，避开右侧障碍物
    # Optimal: d_end = 0.5 (Nudge left)
    x_n = x / 50.0
    y_opt = 0.5 * (3 * x_n**2 - 2 * x_n**3)
    ax.plot(x, y_opt, color='#2ca02c', linewidth=3, label='Optimal Trajectory (Min Cost)')

    # 4. 绘制 EGO 车辆 (原点)
    ego_car = patches.Rectangle((-2, -1), 4, 2, linewidth=1, edgecolor='black', facecolor='#1f77b4', alpha=0.8, label='Ego Vehicle')
    ax.add_patch(ego_car)

    # 5. 绘制障碍物 (Obstacle)
    # 修改障碍物位置，让它离中间远一点，为最优轨迹留出安全空间
    obs_x, obs_y = 30, 1.2
    obs_radius = 1.5
    # 障碍物实体
    obstacle = patches.Circle((obs_x, obs_y), obs_radius, linewidth=1, edgecolor='darkred', facecolor='#d62728', alpha=0.7, label='Static Obstacle')
    ax.add_patch(obstacle)
    # 障碍物膨胀圈 (Collision Risk Zone)
    risk_zone = patches.Circle((obs_x, obs_y), obs_radius + 1.0, linewidth=1, edgecolor='red', facecolor='none', linestyle='--')
    ax.add_patch(risk_zone)
    ax.text(obs_x, obs_y + 3, 'Collision Risk Zone', fontsize=9, color='red', ha='center')

    # 6. 装饰与标注
    ax.set_xlabel('Longitudinal Distance $s$ (m)', fontweight='bold')
    ax.set_ylabel('Lateral Offset $d$ (m)', fontweight='bold')
    ax.set_title('Constraint-Aware Lattice MPC Sampling', pad=15)
    
    # 标注采样逻辑
    ax.annotate(r'Lateral Sampling $\mathcal{D}$', xy=(45, 3), xytext=(40, 6), 
                arrowprops=dict(arrowstyle='->', connectionstyle="arc3,rad=.2"))

    ax.set_ylim(-5, 8)
    ax.set_xlim(-5, 55)
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(loc='upper left', framealpha=0.9, fontsize=9, ncol=2)
    
    plt.tight_layout()
    
    # Save to correct path
    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'docs/figures/lattice_schematic.pdf')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300)
    print(f"Saved lattice schematic to {output_path}")

if __name__ == "__main__":
    draw_lattice_schematic()
