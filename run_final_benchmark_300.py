import os
import time
import subprocess
import sys
import csv
import argparse


def parse_result_csv(csv_path: str):
    stats = {"Success": 0, "Collision": 0, "Lost": 0, "SetupFail": 0, "ValidDegradation": 0}
    total_rows = 0
    jerk_sum = 0.0
    jerk_count = 0

    if not csv_path or not os.path.exists(csv_path):
        return {
            "episodes_completed": 0,
            "success": 0,
            "collision": 0,
            "lost": 0,
            "setupfail": 0,
            "validdegradation": 0,
            "mean_jerk": "",
        }

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            res = (row.get("Result") or "").strip()
            if res in stats:
                stats[res] += 1

            jerk_str = (row.get("Jerk") or "").strip()
            if jerk_str:
                try:
                    jerk_sum += float(jerk_str)
                    jerk_count += 1
                except ValueError:
                    pass

    mean_jerk = (jerk_sum / jerk_count) if jerk_count > 0 else ""
    return {
        "episodes_completed": total_rows,
        "success": stats["Success"],
        "collision": stats["Collision"],
        "lost": stats["Lost"],
        "setupfail": stats["SetupFail"],
        "validdegradation": stats["ValidDegradation"],
        "mean_jerk": mean_jerk,
    }


def append_summary_row(summary_csv_path: str, row: dict):
    os.makedirs(os.path.dirname(summary_csv_path), exist_ok=True)
    header = [
        "timestamp",
        "experiment",
        "script",
        "result_csv",
        "status",
        "episodes_target",
        "episodes_completed",
        "success",
        "collision",
        "lost",
        "mean_jerk",
    ]

    file_exists = os.path.exists(summary_csv_path)
    with open(summary_csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not file_exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in header})

def run_experiment(script_path, experiment_name, episodes=300):
    print(f"\n{'='*60}")
    print(f"STARTING EXPERIMENT: {experiment_name}")
    print(f"Target Episodes: {episodes}")
    print(f"{'='*60}\n")
    
    start_time = time.time()
    
    # Use the active interpreter so the script is portable across machines.
    python_exe = sys.executable
    
    # Ensure environment variables are set for stability
    env = os.environ.copy()
    env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    
    log_root = os.path.join("scripts", "experiments", "final_300", "logs")
    os.makedirs(log_root, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in experiment_name)
    ts = time.strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_root, f"{ts}_{safe_name}.log")
    
    cmd = [
        python_exe, 
        script_path, 
        "--num-episodes", str(episodes)
    ]
    
    try:
        # Run process and stream output
        with open(log_path, "w", encoding="utf-8") as lf:
            lf.write(f"EXPERIMENT: {experiment_name}\n")
            lf.write(f"SCRIPT: {script_path}\n")
            lf.write(f"CMD: {' '.join(cmd)}\n")
            lf.write(f"START_TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            lf.write("=" * 60 + "\n\n")
            lf.flush()
            
            process = subprocess.Popen(
                cmd, 
                env=env,
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            for line in process.stdout:
                print(line, end='')
                lf.write(line)
                lf.flush()
            
            process.wait()
        
        if process.returncode != 0:
            print(f"\n[ERROR] Experiment {experiment_name} failed with exit code {process.returncode}")
            print(f"[ERROR] Log saved to: {log_path}")
            return False
            
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Failed to execute {experiment_name}: {e}")
        print(f"[CRITICAL ERROR] Log saved to: {log_path}")
        return False
        
    duration = (time.time() - start_time) / 3600.0
    print(f"\n[SUCCESS] Experiment {experiment_name} completed in {duration:.2f} hours.")
    print(f"[SUCCESS] Log saved to: {log_path}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-episodes", type=int, default=300)
    args, _ = parser.parse_known_args()
    target_episodes = args.num_episodes

    print("Initializing T-IV Final Benchmark (N=300)...")
    print("Estimated Duration: 6-9 Hours")
    print("Auto-Shutdown: DISABLED (Please manually close after completion)")
    
    summary_csv = os.path.join("scripts", "experiments", "final_300", "summary.csv")
    experiments = [
        ("scripts/experiments/modular_pid/run_eval.py", "Modular PID (Industrial Baseline)", "scripts/experiments/final_300/results_modular_pid.csv"),
        ("scripts/experiments/standard_kf/run_eval.py", "Standard KF (Ablation)", "scripts/experiments/final_300/results_std_kf.csv"),
        ("scripts/experiments/final_300/run_eval_ours.py", "QGIP-Net (Ours - Proposed)", "scripts/experiments/final_300/results_ours.csv"),
    ]
    
    results = {}
    
    for script, name, result_csv in experiments:
        start_ts = time.strftime("%Y-%m-%d %H:%M:%S")
        success = run_experiment(script, name, episodes=target_episodes)
        results[name] = "COMPLETED" if success else "FAILED"
        stats = parse_result_csv(result_csv)
        append_summary_row(
            summary_csv,
            {
                "timestamp": start_ts,
                "experiment": name,
                "script": script,
                "result_csv": result_csv,
                "status": "COMPLETED" if success else "FAILED",
                "episodes_target": target_episodes,
                "episodes_completed": stats["episodes_completed"],
                "success": stats["success"],
                "collision": stats["collision"],
                "lost": stats["lost"],
                "mean_jerk": stats["mean_jerk"] if stats["mean_jerk"] != "" else "",
            },
        )
        
        # Optional: Cool-down between runs to protect GPU
        print("Cooling down for 60 seconds...")
        time.sleep(60)
        
    print("\n" + "="*60)
    print("ALL EXPERIMENTS FINISHED")
    print("Summary:")
    for name, status in results.items():
        print(f"{name}: {status}")
    print("="*60)
