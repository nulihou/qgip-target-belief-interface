#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
填充论文归档目录：复制所有最终可用于投稿的文件
"""

import os
import shutil
import json
import subprocess
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "paper_artifacts_v1"

# 文件复制映射：(源路径, 目标路径)
FILE_MAPPINGS = [
    # === repro/ ===
    # (这些需要手动创建或从git获取)
    
    # === main/logs/ ===
    ("logs_v2/proto_main_eval/gs_proto_driven_30x5_fixed_150.jsonl", "main/logs/gs.jsonl"),
    ("logs_v2/proto_main_eval/random_proto_driven_30x5_fixed_150.jsonl", "main/logs/random.jsonl"),
    ("logs_v2/proto_main_eval/oracle_proto_driven_30x5_improved_v7_dockguard_orbit_fixed.jsonl", "main/logs/oracle.jsonl"),
    
    # === main/seeds/ ===
    ("exp_semantic_critical_short/configs/random_seeds_semcrit.json", "main/seeds/random_seeds.json"),
    
    # === main/tables/ ===
    ("results/proto_main_eval/main_results_table_v7.md", "main/tables/main_results_table.md"),
    ("results/proto_main_eval/main_results_table_v7.tex", "main/tables/main_results_table.tex"),
    
    # === main/figs/ ===
    ("results/proto_main_eval/fig_semnavsucc_bar_v6.png", "main/figs/fig_semnavsucc_bar.png"),
    
    # === main/figs/diagnosis_2x2/ ===
    ("results/proto_main_eval/diagnosis_2x2_v7/gs_2x2_semantic_8m.png", "main/figs/diagnosis_2x2/gs_2x2_semantic_8m.png"),
    ("results/proto_main_eval/diagnosis_2x2_v7/gs_2x2_semantic_8m.md", "main/figs/diagnosis_2x2/gs_2x2_semantic_8m.md"),
    ("results/proto_main_eval/diagnosis_2x2_v7/random_2x2_semantic_8m.png", "main/figs/diagnosis_2x2/random_2x2_semantic_8m.png"),
    ("results/proto_main_eval/diagnosis_2x2_v7/random_2x2_semantic_8m.md", "main/figs/diagnosis_2x2/random_2x2_semantic_8m.md"),
    ("results/proto_main_eval/diagnosis_2x2_v7/oracle_2x2_semantic_8m.png", "main/figs/diagnosis_2x2/oracle_2x2_semantic_8m.png"),
    ("results/proto_main_eval/diagnosis_2x2_v7/oracle_2x2_semantic_8m.md", "main/figs/diagnosis_2x2/oracle_2x2_semantic_8m.md"),
    
    # === oracle/tables/ ===
    ("results/proto_main_eval/oracle_control_improvement_table_v7_unified.md", "oracle/tables/oracle_control_improvement_table.md"),
    ("results/proto_main_eval/oracle_control_improvement_table_v7_unified.tex", "oracle/tables/oracle_control_improvement_table.tex"),
    
    # === oracle/reports/ ===
    ("results/proto_main_eval/oracle_failure_report_v7.md", "oracle/reports/oracle_failure_report.md"),
    
    # === oracle/figs/ ===
    ("results/proto_main_eval/oracle_failure_analysis/oracle_failure_reasons.png", "oracle/figs/oracle_failure_reasons.png"),
    
    # === semantic/semcrit/data/ ===
    ("exp_semantic_critical_short/data/scenarios_semcrit.json", "semantic/semcrit/data/scenarios_semcrit.json"),
    
    # === semantic/semcrit/logs/ ===
    ("exp_semantic_critical_short/logs/gs_semcrit.jsonl", "semantic/semcrit/logs/gs.jsonl"),
    ("exp_semantic_critical_short/logs/random_semcrit.jsonl", "semantic/semcrit/logs/random.jsonl"),
    ("exp_semantic_critical_short/logs/geom_only_semcrit_trained.jsonl", "semantic/semcrit/logs/geom_only.jsonl"),
    
    # === semantic/semcrit/tables/ ===
    ("exp_semantic_critical_short/results/semcrit_table.md", "semantic/semcrit/tables/semcrit_table.md"),
    ("exp_semantic_critical_short/results/semcrit_table.tex", "semantic/semcrit/tables/semcrit_table.tex"),
    
    # === semantic/semcrit/reports/ ===
    ("exp_semantic_critical_short/results/semcrit_report.md", "semantic/semcrit/reports/semcrit_report.md"),
    
    # === semantic/queryflip/data/ ===
    ("exp_semantic_critical_short/data/scenarios_queryflip_test_group.json", "semantic/queryflip/data/scenarios_queryflip_v1.json"),
    ("exp_semantic_critical_short/data/scenarios_queryflip_test_group_v2.json", "semantic/queryflip/data/scenarios_queryflip_v2.json"),
    ("exp_semantic_critical_short/data/scenarios_queryflip_hard.json", "semantic/queryflip/data/scenarios_queryflip_hard.json"),
    ("exp_semantic_critical_short/data/scenarios_queryflip_ultra_hard.json", "semantic/queryflip/data/scenarios_queryflip_ultra_hard.json"),
    
    # === semantic/queryflip/models/finetune_B/ ===
    ("exp_semantic_critical_short/outputs_queryflip_B_v1/best.pt", "semantic/queryflip/models/finetune_B/best.pt"),
    ("exp_semantic_critical_short/outputs_queryflip_B_v1/last.pt", "semantic/queryflip/models/finetune_B/last.pt"),
    # meta.json 需要从checkpoint提取或手动创建
    
    # === semantic/queryflip/results/ ===
    ("exp_semantic_critical_short/results/queryflip_test_B_v1.json", "semantic/queryflip/results/normal_v1.json"),
    ("exp_semantic_critical_short/results/queryflip_test_B_v1_noquery.json", "semantic/queryflip/results/noquery_v1.json"),
    ("exp_semantic_critical_short/results/queryflip_test_B_v1_swap.json", "semantic/queryflip/results/queryswap_v1.json"),
    ("exp_semantic_critical_short/results/queryflip_test_B_v1_v2.json", "semantic/queryflip/results/normal_v2.json"),
    ("exp_semantic_critical_short/results/queryflip_hard_normal.json", "semantic/queryflip/results/hard_eval.json"),
    ("exp_semantic_critical_short/results/queryflip_ultra_hard_normal.json", "semantic/queryflip/results/ultrahard_eval.json"),
    ("exp_semantic_critical_short/results/queryflip_difficulty_analysis.json", "semantic/queryflip/results/difficulty_stats.json"),
    
    # === semantic/queryflip/tables/ ===
    ("exp_semantic_critical_short/results/queryflip_paper_table.md", "semantic/queryflip/tables/queryflip_table.md"),
    ("exp_semantic_critical_short/results/queryflip_table.tex", "semantic/queryflip/tables/queryflip_table.tex"),
    ("exp_semantic_critical_short/results/difficulty_progression_table.md", "semantic/queryflip/tables/difficulty_progression_table.md"),
    ("exp_semantic_critical_short/results/difficulty_progression_table.tex", "semantic/queryflip/tables/difficulty_progression_table.tex"),
    
    # === semantic/queryflip/reports/ ===
    ("exp_semantic_critical_short/outputs_queryflip_B_v1/FINAL_ALL_COMPLETE.md", "semantic/queryflip/reports/semantic_necessity_verification_onepage.md"),
]

def copy_file(src, dst):
    """复制文件"""
    src_path = PROJECT_ROOT / src
    dst_path = ARTIFACTS_DIR / dst
    
    if not src_path.exists():
        print(f"  [WARN] Source not found: {src}")
        return False
    
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, dst_path)
    print(f"  [OK] {dst}")
    return True

def copy_directory(src, dst):
    """复制目录（仅复制文件，不复制子目录结构）"""
    src_path = PROJECT_ROOT / src
    dst_path = ARTIFACTS_DIR / dst
    
    if not src_path.exists():
        print(f"  [WARN] Source directory not found: {src}")
        return False
    
    dst_path.mkdir(parents=True, exist_ok=True)
    
    # 复制所有文件
    for file_path in src_path.rglob("*"):
        if file_path.is_file():
            rel_path = file_path.relative_to(src_path)
            dst_file = dst_path / rel_path
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, dst_file)
            print(f"  [OK] {dst}/{rel_path}")
    
    return True

def get_git_info():
    """获取git信息"""
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT).decode().strip()
        return commit
    except:
        return "unknown"

def create_repro_files():
    """创建复现信息文件"""
    repro_dir = ARTIFACTS_DIR / "repro"
    
    # commit.txt
    commit = get_git_info()
    with open(repro_dir / "commit.txt", "w") as f:
        f.write(commit + "\n")
    print(f"  [OK] repro/commit.txt")
    
    # env.txt (需要手动填写或从系统获取)
    env_info = f"""Python version: {subprocess.check_output(['python', '--version']).decode().strip()}
Created: {datetime.now().isoformat()}
"""
    with open(repro_dir / "env.txt", "w") as f:
        f.write(env_info)
    print(f"  [OK] repro/env.txt")
    
    # carla_version.txt (需要手动填写)
    with open(repro_dir / "carla_version.txt", "w") as f:
        f.write("CARLA version: (please fill in)\n")
    print(f"  [OK] repro/carla_version.txt")
    
    # command_history.md (模板)
    cmd_history = """# Command History

## Main Evaluation
```bash
# GS evaluation
python scripts/online_multi/eval_gs_proto_driven.py ...

# Random evaluation  
python scripts/online_multi/eval_random_proto_driven.py ...

# Oracle evaluation
python scripts/online_multi/eval_oracle_proto_driven.py ...
```

## Semantic Experiments
```bash
# SemCrit evaluation
python exp_semantic_critical_short/scripts/eval_gs_semcrit.py ...

# QueryFlip evaluation
python exp_semantic_critical_short/scripts/eval_query_flip_semcrit.py ...
```

(Please fill in actual commands used)
"""
    with open(repro_dir / "command_history.md", "w") as f:
        f.write(cmd_history)
    print(f"  [OK] repro/command_history.md")

def create_meta_json():
    """创建meta.json（从train_log.jsonl提取）"""
    train_log_path = PROJECT_ROOT / "exp_semantic_critical_short/outputs_queryflip_B_v1/train_log.jsonl"
    meta_path = ARTIFACTS_DIR / "semantic/queryflip/models/finetune_B/meta.json"
    
    if train_log_path.exists():
        # 读取最后一行获取最佳epoch
        with open(train_log_path, "r") as f:
            lines = f.readlines()
            if lines:
                last_line = json.loads(lines[-1])
                best_epoch = last_line.get("epoch", "unknown")
        meta = {
            "best_epoch": best_epoch,
            "checkpoint": "best.pt",
            "created": datetime.now().isoformat(),
        }
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        print(f"  [OK] semantic/queryflip/models/finetune_B/meta.json")
    else:
        print(f"  [WARN] train_log.jsonl not found, creating empty meta.json")
        with open(meta_path, "w") as f:
            json.dump({"best_epoch": "unknown", "checkpoint": "best.pt"}, f, indent=2)

def copy_all_files():
    """复制所有文件"""
    print("Copying files...")
    copied = 0
    failed = 0
    
    for src, dst in FILE_MAPPINGS:
        if copy_file(src, dst):
            copied += 1
        else:
            failed += 1
    
    # 复制protocol目录（可选，如果文件太大可以跳过）
    # copy_directory("exp_semantic_critical_short/protocol_graphs_queryflip_test_group_full", "semantic/queryflip/protocols")
    
    print(f"\nCopied: {copied} files, Failed: {failed} files\n")
    
    # 创建复现文件
    print("Creating repro files...")
    create_repro_files()
    
    # 创建meta.json
    print("\nCreating meta.json...")
    create_meta_json()

if __name__ == "__main__":
    copy_all_files()
