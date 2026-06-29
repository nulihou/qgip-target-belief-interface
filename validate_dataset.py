import os
import sys
import glob
import argparse
import numpy as np
from pathlib import Path
from collections import Counter
from tqdm import tqdm

def validate_multi_candidate(root_dir):
    print(f"Scanning {root_dir} for .npz files...")
    files = sorted(list(Path(root_dir).glob("*.npz")))
    total = len(files)
    print(f"Found {total} files.")
    
    if total == 0:
        print("No files found!")
        return

    stats = {
        "load_fail": 0,
        "schema_error": 0,
        "target_mask_fail": 0,
        "k_dist": Counter(),
        "rel_type_dist": Counter(),
        "scene_type_dist": Counter(),
        "k_ge_5": 0,
        "k_ge_7": 0
    }

    for f in tqdm(files):
        try:
            with np.load(f, allow_pickle=True) as data:
                # Check required keys
                required_keys = ["node_feats", "candidate_mask", "target_index", "rel_type", "num_candidates", "scene_type"]
                for k in required_keys:
                    if k not in data:
                        raise ValueError(f"Missing key: {k}")
                
                # Load data
                node_feats = data["node_feats"]
                candidate_mask = data["candidate_mask"]
                target_index = int(data["target_index"])
                rel_type = int(data["rel_type"])
                num_candidates = int(data["num_candidates"])
                scene_type = int(data["scene_type"])
                
                # Schema/Shape checks
                if len(candidate_mask) != len(node_feats):
                    raise ValueError(f"Shape mismatch: mask {len(candidate_mask)} vs feats {len(node_feats)}")
                
                # Target mask check
                if not (0 <= target_index < len(candidate_mask)):
                     stats["target_mask_fail"] += 1
                elif not candidate_mask[target_index]:
                     stats["target_mask_fail"] += 1
                
                # Stats
                stats["k_dist"][num_candidates] += 1
                stats["rel_type_dist"][rel_type] += 1
                stats["scene_type_dist"][scene_type] += 1
                
                if num_candidates >= 5:
                    stats["k_ge_5"] += 1
                if num_candidates >= 7:
                    stats["k_ge_7"] += 1

        except Exception as e:
            # print(f"Error loading {f.name}: {e}")
            stats["load_fail"] += 1
            if "Missing key" in str(e) or "Shape mismatch" in str(e):
                stats["schema_error"] += 1

    # Report
    print("\n" + "="*50)
    print("VALIDATION REPORT (Multi-Candidate)")
    print("="*50)
    print(f"Total Files: {total}")
    print(f"Load FAIL: {stats['load_fail']}")
    print(f"Schema Errors: {stats['schema_error']}")
    print(f"Target Mask Fail: {stats['target_mask_fail']}")
    print("-" * 30)
    print(f"K >= 5: {stats['k_ge_5']} ({stats['k_ge_5']/total*100:.1f}%)")
    print(f"K >= 7: {stats['k_ge_7']} ({stats['k_ge_7']/total*100:.1f}%)")
    print("-" * 30)
    print("K Distribution:")
    for k in sorted(stats["k_dist"].keys()):
        print(f"  K={k}: {stats['k_dist'][k]}")
    print("-" * 30)
    print("Relation Type Distribution:")
    for r in sorted(stats["rel_type_dist"].keys()):
        print(f"  Type {r}: {stats['rel_type_dist'][r]}")
    print("-" * 30)
    print("Scene Type Distribution:")
    for s in sorted(stats["scene_type_dist"].keys()):
        print(f"  Scene {s}: {stats['scene_type_dist'][s]}")
    print("="*50)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, required=True, help="Data root directory")
    args = parser.parse_args()
    
    if "sequence" in args.root:
        print("Sequence validation not implemented in this quick script yet.")
    else:
        validate_multi_candidate(args.root)

if __name__ == "__main__":
    main()
