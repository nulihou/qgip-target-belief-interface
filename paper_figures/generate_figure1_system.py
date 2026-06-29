import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ArrowStyle

def create_system_architecture_diagram():
    # Set up figure
    fig = plt.figure(figsize=(20, 10), dpi=300)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # Color Palette
    colors = {
        'input': {'fill': '#F5F5F5', 'stroke': '#666666'},
        'neural': {'fill': '#DAE8FC', 'stroke': '#6C8EBF'},
        'symbolic': {'fill': '#FFE6CC', 'stroke': '#D79B00'},
        'ghost': {'fill': '#F8CECC', 'stroke': '#B85450'},
        'control': {'fill': '#D5E8D4', 'stroke': '#82B366'},  # Added green for MPC
        'text': '#333333'
    }

    # Font settings
    font_title = {'family': 'sans-serif', 'weight': 'bold', 'size': 14}
    font_label = {'family': 'sans-serif', 'size': 11}
    font_math = {'family': 'sans-serif', 'style': 'italic', 'size': 10}

    # ==========================================
    # 1. INPUT ZONE (Left)
    # ==========================================
    # Container
    rect_input = FancyBboxPatch((0.5, 1), 3, 8, boxstyle="round,pad=0.2", 
                               fc='white', ec=colors['input']['stroke'], alpha=0.5, linestyle='--')
    ax.add_patch(rect_input)
    ax.text(2, 9.2, "Input Layer", ha='center', **font_title)

    # Sensor Data
    rect_sensor = patches.Rectangle((1, 6.5), 2, 1.5, fc=colors['input']['fill'], ec=colors['input']['stroke'])
    ax.add_patch(rect_sensor)
    ax.text(2, 7.25, "LiDAR/Camera\n(State Obs)", ha='center', va='center', **font_label)

    # Query
    rect_query = patches.Rectangle((1, 3.5), 2, 1.5, fc=colors['input']['fill'], ec=colors['input']['stroke'])
    ax.add_patch(rect_query)
    ax.text(2, 4.25, "Query:\n\"Follow Leader\"", ha='center', va='center', **font_label)

    # ==========================================
    # 2. NEURAL PERCEPTION ZONE (Mid-Left)
    # ==========================================
    # Container
    rect_neural = FancyBboxPatch((4, 1), 4.5, 8, boxstyle="round,pad=0.2", 
                                fc='white', ec=colors['neural']['stroke'], alpha=0.5, linestyle='--')
    ax.add_patch(rect_neural)
    ax.text(6.25, 9.2, "Neural Perception", ha='center', color=colors['neural']['stroke'], **font_title)

    # Scene Graph Construction
    # Draw simple graph
    circle_ego = patches.Circle((5, 7.5), 0.3, fc=colors['neural']['fill'], ec=colors['neural']['stroke'])
    circle_n1 = patches.Circle((6, 8), 0.2, fc='white', ec=colors['neural']['stroke'])
    circle_n2 = patches.Circle((6, 7), 0.2, fc='white', ec=colors['neural']['stroke'])
    circle_n3 = patches.Circle((5, 6.5), 0.2, fc='white', ec=colors['neural']['stroke'])
    
    # Edges
    ax.plot([5, 6], [7.5, 8], color=colors['neural']['stroke'], lw=1)
    ax.plot([5, 6], [7.5, 7], color=colors['neural']['stroke'], lw=1)
    ax.plot([5, 5], [7.5, 6.5], color=colors['neural']['stroke'], lw=1)
    
    ax.add_patch(circle_ego)
    ax.add_patch(circle_n1)
    ax.add_patch(circle_n2)
    ax.add_patch(circle_n3)
    ax.text(5, 7.5, "Ego", ha='center', va='center', size=8)
    ax.text(6.25, 6.2, "Scene Graph", ha='center', **font_label)

    # FiLM Module
    rect_film = patches.Polygon([[5, 4.5], [7.5, 4.5], [7, 3.5], [5.5, 3.5]], closed=True,
                               fc=colors['neural']['fill'], ec=colors['neural']['stroke'])
    ax.add_patch(rect_film)
    ax.text(6.25, 4, "FiLM Modulation\n$\\gamma(q) \\odot h + \\beta(q)$", ha='center', va='center', size=9)

    # GNN/GAT
    rect_gnn = patches.Rectangle((5, 1.5), 2.5, 1.2, fc=colors['neural']['fill'], ec=colors['neural']['stroke'])
    ax.add_patch(rect_gnn)
    ax.text(6.25, 2.1, "GATv2\nAggregation", ha='center', va='center', **font_label)

    # Arrows Input -> Neural
    ax.annotate("", xy=(5, 7.25), xytext=(3, 7.25), arrowprops=dict(arrowstyle="->", color='#4D4D4D'))
    # Query -> FiLM
    ax.annotate("Embed", xy=(5.25, 4), xytext=(3, 4.25), arrowprops=dict(arrowstyle="->", color='#4D4D4D'))
    
    # Internal Neural Arrows
    ax.annotate("", xy=(6.25, 4.5), xytext=(6.25, 6.0), arrowprops=dict(arrowstyle="->", color='#4D4D4D'))
    ax.annotate("", xy=(6.25, 2.7), xytext=(6.25, 3.5), arrowprops=dict(arrowstyle="->", color='#4D4D4D'))

    # ==========================================
    # 3. SYMBOLIC REASONING ZONE (Mid-Right)
    # ==========================================
    # Container
    rect_symbolic = FancyBboxPatch((9, 1), 6, 8, boxstyle="round,pad=0.2", 
                                  fc='white', ec=colors['symbolic']['stroke'], alpha=0.5, linestyle='--')
    ax.add_patch(rect_symbolic)
    ax.text(12, 9.2, "Symbolic Reasoning", ha='center', color=colors['symbolic']['stroke'], **font_title)

    # Switch Diamond
    diamond = patches.Polygon([[10.5, 5], [11.5, 5.8], [12.5, 5], [11.5, 4.2]], closed=True,
                             fc=colors['symbolic']['fill'], ec=colors['symbolic']['stroke'])
    ax.add_patch(diamond)
    ax.text(11.5, 5, "Score > $\\tau$?", ha='center', va='center', **font_label)

    # Arrow Neural -> Switch
    ax.annotate("Score", xy=(10.5, 5), xytext=(7.5, 2.1), arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=-0.1", color='#4D4D4D'))

    # Branch YES (Top)
    rect_update = patches.Rectangle((13, 6.5), 1.8, 1.5, fc=colors['symbolic']['fill'], ec=colors['symbolic']['stroke'])
    ax.add_patch(rect_update)
    ax.text(13.9, 7.25, "Measure Update\n(Kalman Filter)", ha='center', va='center', size=9)
    ax.text(13.9, 6.7, "$x_t = x_{t|t-1} + K\\tilde{y}$", ha='center', va='center', size=8, color='#555')

    # Branch NO (Bottom - Ghost)
    rect_ghost = patches.Rectangle((13, 2), 1.8, 1.5, fc=colors['ghost']['fill'], ec=colors['ghost']['stroke'], linestyle='--')
    ax.add_patch(rect_ghost)
    ax.text(13.9, 2.75, "Ghost Mode\n(Prediction Only)", ha='center', va='center', size=9, weight='bold', color='#B85450')
    ax.text(13.9, 2.2, "$x_{t+1} = F x_t$", ha='center', va='center', size=8, color='#B85450')

    # Connections
    ax.annotate("Yes", xy=(13, 7.25), xytext=(11.5, 5.8), arrowprops=dict(arrowstyle="->", connectionstyle="angle,angleA=0,angleB=90,rad=5", color='#4D4D4D'))
    ax.annotate("No", xy=(13, 2.75), xytext=(11.5, 4.2), arrowprops=dict(arrowstyle="->", connectionstyle="angle,angleA=0,angleB=-90,rad=5", color='#4D4D4D'))

    # Merge to Output
    circle_merge = patches.Circle((16, 5), 0.1, fc='black')
    ax.add_patch(circle_merge)
    
    ax.annotate("", xy=(16, 5), xytext=(14.8, 7.25), arrowprops=dict(arrowstyle="->", color='#4D4D4D'))
    ax.annotate("", xy=(16, 5), xytext=(14.8, 2.75), arrowprops=dict(arrowstyle="->", color='#4D4D4D'))

    # ==========================================
    # 4. CONTROL ZONE (Right)
    # ==========================================
    # Container
    rect_control = FancyBboxPatch((16.5, 1), 3, 8, boxstyle="round,pad=0.2", 
                                 fc='white', ec=colors['control']['stroke'], alpha=0.5, linestyle='--')
    ax.add_patch(rect_control)
    ax.text(18, 9.2, "Control Layer", ha='center', color=colors['control']['stroke'], **font_title)

    # MPC Box
    rect_mpc = patches.Rectangle((17, 3), 2, 4, fc=colors['control']['fill'], ec=colors['control']['stroke'])
    ax.add_patch(rect_mpc)
    ax.text(18, 6.5, "Hard-Constraint\nMPC", ha='center', va='center', weight='bold', size=10)
    
    # Simple MPC sketch
    ax.plot([17.5, 18, 18.5], [3.5, 5, 6], 'g-', lw=2) # Trajectory
    circle_obs = patches.Circle((17.8, 5.2), 0.1, fc='red', alpha=0.5) # Obstacle
    ax.add_patch(circle_obs)
    ax.text(18, 3.2, "Optimal Traj.", ha='center', size=8)

    # Input to MPC
    ax.annotate("Target State $x_t$", xy=(17, 5), xytext=(16, 5), arrowprops=dict(arrowstyle="->", color='#4D4D4D'))

    # Output
    ax.annotate("Steer / Accel", xy=(19.5, 5), xytext=(19, 5), arrowprops=dict(arrowstyle="->", color='#4D4D4D', lw=2))

    # Save
    plt.tight_layout()
    plt.savefig('d:/project/lc_org_v2.0/paper_figures/system_architecture.png', bbox_inches='tight', dpi=300)
    plt.savefig('d:/project/lc_org_v2.0/paper_figures/system_architecture.pdf', bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    create_system_architecture_diagram()
