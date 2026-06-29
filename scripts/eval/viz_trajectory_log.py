import pickle
import matplotlib.pyplot as plt
import numpy as np
import os

def viz_trajectory_log(log_path="trajectory_log.pkl"):
    if not os.path.exists(log_path):
        print(f"Log file not found: {log_path}")
        return

    with open(log_path, "rb") as f:
        data = pickle.load(f)
        
    ego_traj = np.array(data["ego"])
    target_traj = np.array(data["target"])
    obstacle = data["obstacle"]
    
    print(f"Loaded {len(ego_traj)} steps.")
    
    plt.figure(figsize=(10, 10))
    
    # 1. Plot Trajectories
    plt.plot(ego_traj[:, 0], ego_traj[:, 1], 'b-', linewidth=2, label='Ego (QGIP)')
    plt.plot(target_traj[:, 0], target_traj[:, 1], 'g--', linewidth=2, label='Target')
    
    # Start/End
    plt.scatter(ego_traj[0, 0], ego_traj[0, 1], c='blue', marker='o', s=100, label='Start')
    plt.scatter(ego_traj[-1, 0], ego_traj[-1, 1], c='blue', marker='x', s=100, label='End')
    
    # 2. Plot Obstacle
    if obstacle:
        plt.scatter(obstacle[0], obstacle[1], c='red', marker='s', s=200, label='Obstacle (Static)')
        # Add safety radius circle
        circle = plt.Circle(obstacle, 2.5, color='red', fill=False, linestyle=':')
        plt.gca().add_patch(circle)
        
    plt.title("Scenario B: Emergent Obstacle Avoidance (Closed-Loop)", fontsize=14)
    plt.xlabel("Global X (m)")
    plt.ylabel("Global Y (m)")
    plt.legend()
    plt.grid(True)
    plt.axis('equal')
    
    os.makedirs("docs/viz_paper", exist_ok=True)
    save_path = "docs/viz_paper/figure_y_avoidance.png"
    plt.savefig(save_path, dpi=300)
    print(f"Saved figure to {save_path}")
    plt.close()

if __name__ == "__main__":
    viz_trajectory_log()
