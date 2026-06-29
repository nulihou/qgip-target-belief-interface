import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.eval.run_batch_stats import BatchEvaluator
from scripts.eval.baselines.run_baseline_ablation import QGIPAgent as AblationAgent

if __name__ == "__main__":
    print(">>> RUNNING ABLATION (NO KF) BASELINE (N=300) <<<")
    evaluator = BatchEvaluator(agent_class=AblationAgent)
    evaluator.run_benchmark(num_episodes=300, log_file="docs/experiments/01_main_town05/baseline_nokf_300.csv")
