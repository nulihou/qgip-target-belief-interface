import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.eval.run_batch_stats import BatchEvaluator
from scripts.eval.baselines.run_baseline_rule import QGIPAgent as RuleAgent

if __name__ == "__main__":
    print(">>> RUNNING RULE-BASED BASELINE (N=300) <<<")
    evaluator = BatchEvaluator(agent_class=RuleAgent)
    evaluator.run_benchmark(num_episodes=300, log_file="docs/experiments/01_main_town05/baseline_rule_300.csv")
