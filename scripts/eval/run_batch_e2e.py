import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.eval.run_batch_stats import BatchEvaluator
from scripts.eval.baselines.run_baseline_e2e import QGIPAgent as E2EAgent

if __name__ == "__main__":
    print(">>> RUNNING E2E BASELINE (N=300) <<<")
    evaluator = BatchEvaluator(agent_class=E2EAgent)
    evaluator.run_benchmark(num_episodes=300, log_file="docs/experiments/01_main_town05/baseline_e2e_300.csv")
