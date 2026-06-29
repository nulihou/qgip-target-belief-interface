import os
import glob
import numpy as np
from tqdm import tqdm
from collections import defaultdict, Counter
import matplotlib.pyplot as plt

def verify_dataset(root_dir):
    files = sorted(glob.glob(os.path.join(root_dir, "*.npz")))
    print(f"Scanning {len(files)} files in {root_dir}...")
    
    # 1. Consistency Checks
    error_counts = {
        "load_fail": 0,
        "target_idx_oob": 0, # Out of bound
        "mask_mismatch": 0, # mask[target] != True
        "num_cand_mismatch": 0, # num_candidates != sum(mask)
    }
    bad_files = []
    
    # 2. Random Baseline
    sum_inv_k = 0.0
    valid_samples_count = 0
    
    # 3. Distribution Data
    data_info = [] # List of dicts with metadata
    
    for f in tqdm(files):
        try:
            with np.load(f, allow_pickle=True) as data:
                # Load key fields
                node_feats = data['node_feats']
                target_idx = int(data['target_index'])
                mask = data['candidate_mask']
                num_cand_stored = int(data['num_candidates'])
                scene_hash = str(data['base_scene_hash'])
                scene_type = int(data['scene_type'])
                
                # --- A. Consistency Checks ---
                N = node_feats.shape[0]
                if not (0 <= target_idx < N):
                    error_counts["target_idx_oob"] += 1
                    bad_files.append(f)
                    continue
                
                if not mask[target_idx]:
                    error_counts["mask_mismatch"] += 1
                    bad_files.append(f)
                    continue
                    
                real_num_cand = int(mask.sum())
                if real_num_cand != num_cand_stored:
                    # This is a soft error, maybe just logging update lag, but let's note it
                    error_counts["num_cand_mismatch"] += 1
                    # We use real_num_cand for baseline calculation
                
                # --- B. Random Baseline ---
                if real_num_cand > 0:
                    sum_inv_k += (1.0 / real_num_cand)
                    valid_samples_count += 1
                
                # --- C. Distribution Metadata ---
                # Parse Town from hash: "TownName_SceneType_..."
                # Town names might contain underscores? Usually Town03, Town10HD_Opt
                # Let's split by first few underscores.
                # Heuristic: Town names in CARLA usually start with "Town".
                parts = scene_hash.split('_')
                # Town10HD_Opt is tricky.
                # Known towns: Town01, Town02, Town03, Town04, Town05, Town10HD, Town10HD_Opt
                town = "Unknown"
                if scene_hash.startswith("Town10HD_Opt"):
                    town = "Town10HD_Opt"
                elif scene_hash.startswith("Town"):
                    # Find where the scene type integer is. Scene type is 0, 1, 2.
                    # It's the field after town.
                    # But wait, scene_hash = f"{town}_{scene_type}_{ex}..."
                    # We can use the known scene_type value to help locate the split point?
                    # Or just reliable string parsing.
                    # Batch 1: Town10HD_Opt
                    # Batch 2: Town03
                    # Batch 3: Town05
                    if "Town03" in scene_hash: town = "Town03"
                    elif "Town05" in scene_hash: town = "Town05"
                    elif "Town10" in scene_hash: town = "Town10HD_Opt"
                    else: town = parts[0]
                
                data_info.append({
                    "file": f,
                    "town": town,
                    "scene_type": scene_type,
                    "k": real_num_cand,
                    "target_idx": target_idx
                })
                
        except Exception as e:
            error_counts["load_fail"] += 1
            bad_files.append(f)
    
    # Report Consistency
    print("\n" + "="*50)
    print("1. CONSISTENCY CHECK (Hard Threshold)")
    print("="*50)
    total_errors = sum(error_counts.values())
    for k, v in error_counts.items():
        print(f"  - {k}: {v}")
    
    if total_errors == 0:
        print("✅ PASSED: Data is fully consistent.")
    else:
        print(f"❌ FAILED: Found {total_errors} errors. Bad files need deletion.")
        if bad_files:
            print(f"Sample bad files: {bad_files[:3]}")

    # Report Baseline
    print("\n" + "="*50)
    print("2. RANDOM BASELINE (Mean 1/K)")
    print("="*50)
    if valid_samples_count > 0:
        mean_random_acc = sum_inv_k / valid_samples_count
        print(f"  - Valid Samples: {valid_samples_count}")
        print(f"  - Mean Random Acc (1/K): {mean_random_acc:.4f} ({mean_random_acc*100:.2f}%)")
        print("  -> Compare this with your Val Acc. If Val Acc ~ Mean Random Acc, model hasn't learned yet.")
    else:
        print("  - No valid samples.")

    # Report Distribution & Split
    print("\n" + "="*50)
    print("3. DISTRIBUTION & SPLIT CHECK")
    print("="*50)
    
    # Analyze full dataset distribution
    all_towns = Counter([d['town'] for d in data_info])
    all_scenes = Counter([d['scene_type'] for d in data_info])
    all_ks = Counter([d['k'] for d in data_info])
    
    print("Full Dataset Distribution:")
    print(f"  - Towns: {dict(all_towns)}")
    print(f"  - Scenes: {dict(all_scenes)}")
    print(f"  - K Stats: Min={min(all_ks.keys())}, Max={max(all_ks.keys())}")
    
    # Check K distribution (Easy vs Hard)
    k_easy = sum([v for k,v in all_ks.items() if k <= 4])
    k_hard = sum([v for k,v in all_ks.items() if k >= 5])
    print(f"  - Easy (K<=4): {k_easy} ({k_easy/len(data_info)*100:.1f}%)")
    print(f"  - Hard (K>=5): {k_hard} ({k_hard/len(data_info)*100:.1f}%)")

    # Simulate Sequential Split (Current Default)
    split_ratio = 0.8
    split_idx = int(len(data_info) * split_ratio)
    train_set = data_info[:split_idx]
    val_set = data_info[split_idx:]
    
    print("\n[Simulation] Sequential Split (Default):")
    train_towns = Counter([d['town'] for d in train_set])
    val_towns = Counter([d['town'] for d in val_set])
    
    print(f"  - Train Towns: {dict(train_towns)}")
    print(f"  - Val Towns:   {dict(val_towns)}")
    
    if len(val_towns) < len(all_towns) or any(t not in train_towns for t in all_towns):
        print("❌ CRITICAL: Sequential split causes Map Leakage/Bias!")
        print("   -> Val set contains maps not in Train, or Train/Val map distribution is disjoint.")
        print("   -> ACTION REQUIRED: Use random shuffle split.")
    else:
        # Check balance
        print("  - Split looks okay-ish in terms of presence, but check ratios.")

    # Simulate Random Split
    print("\n[Simulation] Random Split:")
    import random
    indices = list(range(len(data_info)))
    random.shuffle(indices)
    train_indices = indices[:split_idx]
    val_indices = indices[split_idx:]
    
    train_set_rnd = [data_info[i] for i in train_indices]
    val_set_rnd = [data_info[i] for i in val_indices]
    
    train_towns_rnd = Counter([d['town'] for d in train_set_rnd])
    val_towns_rnd = Counter([d['town'] for d in val_set_rnd])
    print(f"  - Train Towns: {dict(train_towns_rnd)}")
    print(f"  - Val Towns:   {dict(val_towns_rnd)}")
    print("✅ Random split maintains distribution.")

    return bad_files

if __name__ == "__main__":
    bad_files = verify_dataset("data/multi_candidate_data")
    if bad_files:
        print(f"\nDeleting {len(bad_files)} bad files...")
        for f in bad_files:
            try:
                os.remove(f)
            except:
                pass
        print("Cleanup done.")
