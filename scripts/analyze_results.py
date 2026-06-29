import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import glob
import os

def analyze_metrics():
    # 1. Load Data
    print("Loading metrics...")
    
    # Load Ours
    try:
        df_ours = pd.read_csv("eval_metrics.csv")
        df_ours["Method"] = "Ours (Full)"
    except Exception as e:
        print(f"Error reading eval_metrics.csv: {e}")
        return

    # Load E2E Baseline
    try:
        df_e2e = pd.read_csv("eval_metrics_exp5_e2e.csv")
        df_e2e["Method"] = "Baseline (E2E)"
        # Rename columns to match
        df_e2e = df_e2e.rename(columns={
            "Collision Occurred": "Collision",
            "Avg Jerk (m/s^3)": "AvgJerk",
            "Avg Lateral Error (approx)": "LatDeviation"
        })
        # Ensure columns exist
        if "SteeringEntropy" not in df_e2e.columns:
            df_e2e["SteeringEntropy"] = np.nan
    except Exception as e:
        print(f"Error reading e2e metrics: {e}")
        df_e2e = pd.DataFrame()

    # Combine
    df = pd.concat([df_ours, df_e2e], ignore_index=True)

    # 2. Comparison Table
    print("\n=== Core Comparison Table (Section IV) ===")
    summary = df.groupby("Method").agg({
        "Success": "mean",
        "Collision": "mean",
        "FollowingRMSE": "mean",
        "AvgJerk": "mean",
        "SteeringEntropy": "mean",
        "LatDeviation": "mean"
    }).reset_index()
    
    # Format nicely
    summary_print = summary.copy()
    summary_print["Success"] = (summary_print["Success"] * 100).map("{:.1f}%".format)
    summary_print["Collision"] = (summary_print["Collision"] * 100).map("{:.1f}%".format)
    summary_print["FollowingRMSE"] = summary_print["FollowingRMSE"].map("{:.2f}".format)
    summary_print["AvgJerk"] = summary_print["AvgJerk"].map("{:.2f}".format)
    summary_print["SteeringEntropy"] = summary_print["SteeringEntropy"].map("{:.4f}".format)
    summary_print["LatDeviation"] = summary_print["LatDeviation"].map("{:.3f}".format)
    
    print(summary_print.to_string(index=False))
    
    # Save Table
    summary_print.to_csv("comparison_table.csv", index=False)
    
    # 3. Box Plots
    print("\nGenerating Box Plots...")
    try:
        plt.figure(figsize=(12, 5))
        
        # Filter for BoxPlot (Drop NaNs if any)
        df_plot = df.dropna(subset=["FollowingRMSE", "AvgJerk"])
        
        plt.subplot(1, 2, 1)
        methods = df_plot["Method"].unique()
        data_rmse = [df_plot[df_plot["Method"] == m]["FollowingRMSE"].values for m in methods]
        plt.boxplot(data_rmse, labels=methods)
        plt.title("Following RMSE (Lower is Better)")
        plt.ylabel("RMSE (m)")
        plt.grid(True, linestyle='--', alpha=0.6)
        
        plt.subplot(1, 2, 2)
        data_jerk = [df_plot[df_plot["Method"] == m]["AvgJerk"].values for m in methods]
        plt.boxplot(data_jerk, labels=methods)
        plt.title("Average Jerk (Lower is Better)")
        plt.ylabel("Jerk (m/s^3)")
        plt.grid(True, linestyle='--', alpha=0.6)
        
        plt.tight_layout()
        plt.savefig("results_boxplot.png")
        print("Saved results_boxplot.png")
    except Exception as e:
        print(f"Failed to plot boxplots: {e}")

    # 4. Time Series Plot
    print("\nGenerating Time Series Plot...")
    try:
        # Load Representative Episode (e.g., Episode 0 or first successful one)
        # Find a successful episode from Ours
        succ_ep = df_ours[df_ours["Success"] == 1]["Episode"].min()
        if pd.isna(succ_ep):
             succ_ep = 0 # Fallback
        else:
             succ_ep = int(succ_ep) - 1 # Episode 1 -> Index 0
             
        log_file = f"episode_log_{succ_ep}.csv"
        if not os.path.exists(log_file):
            # Try finding any log
            logs = glob.glob("episode_log_*.csv")
            if logs:
                log_file = logs[0]
            else:
                print("No episode logs found for time series.")
                return

        print(f"Using {log_file} for Time Series visualization")
        df_ts = pd.read_csv(log_file)
        
        plt.figure(figsize=(10, 6))
        
        # Plot Distance to Target
        # timestamps vs dist_to_target
        if "timestamps" in df_ts.columns and "dist_to_target" in df_ts.columns:
            plt.plot(df_ts["timestamps"], df_ts["dist_to_target"], label="Ours (Neuro-Symbolic)", color='green', linewidth=2)
            
            # Add ideal distance line
            plt.axhline(y=12.0, color='blue', linestyle=':', label="Ideal Distance (12m)")
            
            # Add "Safe Distance" zone
            plt.axhspan(10, 14, color='blue', alpha=0.1, label="Safe Zone")
            
            plt.xlabel("Time (s)")
            plt.ylabel("Following Distance (m)")
            plt.title(f"Time-Series Response (Episode {succ_ep+1})")
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            plt.savefig("results_timeseries.png")
            print("Saved results_timeseries.png")
        else:
            print("Columns missing in episode log for time series.")

    except Exception as e:
        print(f"Failed to plot time series: {e}")

if __name__ == "__main__":
    analyze_metrics()
