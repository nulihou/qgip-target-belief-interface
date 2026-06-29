import os
import glob
import numpy as np
import argparse
import math

def run_baseline(data_dir):
    files = glob.glob(os.path.join(data_dir, "*.npz"))
    if not files:
        print(f"No files found in {data_dir}")
        return

    total = 0
    correct = 0
    
    # Distance stats
    target_dists = [] # Distance of the TRUE target from Ego
    min_distractor_dists = [] # Distance of the CLOSEST distractor from Ego
    
    # Disturbance stats (Target to Nearest Distractor)
    target_to_distractor_dists = []
    
    difficulties = {}

    print(f"Running Baseline (Nearest Neighbor) on {len(files)} samples in {data_dir}...")

    # DEBUG: Inspect first file
    if files:
        f = files[0]
        try:
            data = np.load(f, allow_pickle=True)
            if 'snapshot' in data:
                snapshot = data['snapshot'].item()
                feats = snapshot.get('node_feats') if isinstance(snapshot, dict) else snapshot.x.numpy()
                tgt_idx = int(snapshot.get('target_index', -1)) if isinstance(snapshot, dict) else int(snapshot.target_index)
                
                print(f"\n[DEBUG] Inspecting {os.path.basename(f)}")
                print(f"Target Index: {tgt_idx}")
                print(f"Node Feats Shape: {feats.shape}")
                for i in range(len(feats)):
                    d = feats[i][2]
                    dx = feats[i][0]
                    dy = feats[i][1]
                    role = "TARGET" if i == tgt_idx else "Cand"
                    print(f"  Node {i} ({role}): dx={dx:.2f}, dy={dy:.2f}, dist={d:.2f}")
        except Exception as e:
            print(f"Debug Error: {e}")

    for f in files:
        try:
            data = np.load(f, allow_pickle=True)
            
            # Extract Snapshot
            if 'snapshot' in data:
                snapshot = data['snapshot'].item()
                if isinstance(snapshot, dict):
                    feats = snapshot.get('node_feats')
                    target_idx = int(snapshot.get('target_index', -1))
                else:
                    feats = snapshot.x.numpy()
                    target_idx = int(snapshot.target_index)
            elif 'node_feats' in data:
                feats = data['node_feats']
                target_idx = int(data['target_index'])
            else:
                continue
                
            if feats is None or target_idx == -1:
                continue

            # Difficulty
            diff = str(data['difficulty'])
            difficulties[diff] = difficulties.get(diff, 0) + 1

            # Ego is NOT in feats (feats are relative to Ego)
            # Find Nearest Neighbor to Ego (dist to 0,0)
            
            min_d = 9999.0
            pred_idx = -1
            
            for i in range(len(feats)):
                pos = feats[i][:2]
                dist = math.sqrt(pos[0]**2 + pos[1]**2)
                
                if dist < min_d:
                    min_d = dist
                    pred_idx = i
            
            if pred_idx != -1:
                total += 1
                if pred_idx == target_idx:
                    correct += 1
                
                # Stats
                target_pos = feats[target_idx][:2]
                target_dist_ego = math.sqrt(target_pos[0]**2 + target_pos[1]**2)
                target_dists.append(target_dist_ego)
                
                # Distractor stats
                # Find closest distractor to TARGET
                min_d_to_target = 999.0
                for i in range(len(feats)):
                    if i == target_idx: continue
                    pos = feats[i][:2]
                    d = math.sqrt((pos[0]-target_pos[0])**2 + (pos[1]-target_pos[1])**2)
                    if d < min_d_to_target:
                        min_d_to_target = d
                
                if min_d_to_target < 900:
                    target_to_distractor_dists.append(min_d_to_target)

        except Exception as e:
            print(f"Error processing {f}: {e}")
            continue

    # Breakdown by difficulty
    diff_stats = {}
    
    print("\n" + "="*40)
    print(f"BASELINE RESULTS (Nearest Neighbor)")
    print("="*40)
    print(f"Total Samples: {total}")
    print(f"Overall Accuracy: {acc:.2f}%")
    print(f"Avg Target Dist: {avg_tgt_dist:.2f} m")
    print(f"Avg Disturbance: {avg_disturbance:.2f} m")
    print("-" * 20)
    print("Breakdown by Difficulty:")
    
    # Re-process to group by difficulty (inefficient but fine for small data)
    # Actually we can't re-process easily without storing.
    # Let's just store results in a list
    pass 

def run_baseline_enhanced(data_dir):
    files = glob.glob(os.path.join(data_dir, "*.npz"))
    results = []
    
    for f in files:
        try:
            data = np.load(f, allow_pickle=True)
            if 'snapshot' in data:
                snapshot = data['snapshot'].item()
                feats = snapshot.get('node_feats') if isinstance(snapshot, dict) else snapshot.x.numpy()
                tgt_idx = int(snapshot.get('target_index', -1)) if isinstance(snapshot, dict) else int(snapshot.target_index)
            elif 'node_feats' in data:
                feats = data['node_feats']
                tgt_idx = int(data['target_index'])
            else: continue
            
            diff = str(data['difficulty'])
            
            # Ego logic
            min_d = 9999.0
            pred_idx = -1
            for i in range(len(feats)):
                pos = feats[i][:2]
                dist = math.sqrt(pos[0]**2 + pos[1]**2)
                if dist < min_d:
                    min_d = dist
                    pred_idx = i
            
            is_correct = (pred_idx == tgt_idx)
            
            # Disturbance
            tgt_pos = feats[tgt_idx][:2]
            min_disturb = 999.0
            for i in range(len(feats)):
                if i == tgt_idx: continue
                d = math.sqrt((feats[i][0]-tgt_pos[0])**2 + (feats[i][1]-tgt_pos[1])**2)
                if d < min_disturb: min_disturb = d
            
            results.append({
                'difficulty': diff,
                'correct': is_correct,
                'disturbance': min_disturb
            })
        except: pass

    # Aggregation
    by_diff = {}
    for r in results:
        d = r['difficulty']
        if d not in by_diff: by_diff[d] = {'total': 0, 'correct': 0, 'disturb_sum': 0.0}
        by_diff[d]['total'] += 1
        if r['correct']: by_diff[d]['correct'] += 1
        if r['disturbance'] < 900: by_diff[d]['disturb_sum'] += r['disturbance']

    print("\n" + "="*40)
    print(f"BASELINE RESULTS (Enhanced)")
    print("="*40)
    for d, stats in by_diff.items():
        acc = stats['correct'] / stats['total'] * 100.0
        avg_dist = stats['disturb_sum'] / stats['total']
        print(f"Difficulty: {d}")
        print(f"  Count: {stats['total']}")
        print(f"  Accuracy: {acc:.2f}%")
        print(f"  Avg Disturbance: {avg_dist:.2f} m")
        print("-" * 20)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="data/joint_data_ultra")
    args = parser.parse_args()
    
    run_baseline_enhanced(args.dir)
