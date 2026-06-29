#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查日志文件是否覆盖了完整的(scene_id, run_id)组合"""
import json
import sys

path = sys.argv[1]
R = 5
# run_id可能是0-based (0-4) 或 1-based (1-5)，检查实际范围
with open(path, "r", encoding="utf-8") as f:
    first_line = f.readline().strip()
    if first_line:
        first_json = json.loads(first_line)
        first_run_id = first_json.get("run_id", -1)
        if first_run_id >= 1:
            # 1-based: run_id 1-5
            expected = set((sid, rid) for sid in range(30) for rid in range(1, R+1))
        else:
            # 0-based: run_id 0-4
            expected = set((sid, rid) for sid in range(30) for rid in range(R))
    else:
        expected = set((sid, rid) for sid in range(30) for rid in range(1, R+1))  # 默认1-based

seen = set()
dups = 0

with open(path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        j = json.loads(line)
        key = (j.get("scene_id", j.get("scen_id", -1)), j.get("run_id", -1))
        if key[0] < 0 or key[1] < 0:
            continue
        if key in seen:
            dups += 1
        seen.add(key)

# 计算总行数
with open(path, "r", encoding="utf-8") as f:
    lines = [l.strip() for l in f if l.strip()]
    total_lines = len(lines)

missing = sorted(expected - seen)
extra = sorted(seen - expected)

print("file:", path)
print("lines:", total_lines)
print("unique keys:", len(seen))
print("dups:", dups)
print("missing:", missing)
print("extra:", extra)

if len(seen) == 150 and dups == 0 and len(missing) == 0 and len(extra) == 0:
    print("\n[OK] Coverage check passed: 150 unique keys, no duplicates, no missing, no extra")
else:
    print("\n[FAIL] Coverage check failed")

