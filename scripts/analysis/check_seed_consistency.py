#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查两个日志文件的seed一致性"""
import json
import sys

def load_map(path):
    m = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            j = json.loads(line)
            scene_id = j.get("scene_id", j.get("scen_id", -1))
            run_id = j.get("run_id", -1)
            if scene_id < 0 or run_id < 0:
                continue
            key = (scene_id, run_id)
            m[key] = {
                "seed_id": j.get("seed_id"),
                "carla_seed": j.get("carla_seed"),
                "tm_seed": j.get("traffic_manager_seed"),
                "py": j.get("python_seed", j.get("py_seed")),
                "np": j.get("numpy_seed", j.get("np_seed")),
                "torch": j.get("torch_seed"),
            }
    return m

if len(sys.argv) < 3:
    print("Usage: python check_seed_consistency.py ORACLE_JSONL OTHER_JSONL")
    sys.exit(1)

oracle_path, other_path = sys.argv[1], sys.argv[2]
oracle = load_map(oracle_path)
other = load_map(other_path)

print(f"Oracle keys: {len(oracle)}")
print(f"Other keys: {len(other)}")

bad = []
missing_keys = []
for key in oracle:
    if key not in other:
        missing_keys.append(key)
        bad.append((key, "missing key"))
        continue
    if oracle[key] != other[key]:
        bad.append((key, "mismatch", oracle[key], other[key]))

for key in other:
    if key not in oracle:
        bad.append((key, "extra key in other"))

print(f"\ncompare: {other_path}")
print(f"mismatch count: {len(bad)}")
if bad:
    print("first 10 issues:")
    for x in bad[:10]:
        print(f"  {x}")
    if len(bad) > 10:
        print(f"  ... and {len(bad) - 10} more")
else:
    print("[OK] All seeds match!")

if missing_keys:
    print(f"\n[WARNING] Missing keys in other file: {len(missing_keys)}")
    print(f"First 5: {missing_keys[:5]}")

