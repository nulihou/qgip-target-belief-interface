#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查轨迹数据是否存在"""

import json
from pathlib import Path

def check_file(path):
    print(f"\n检查文件: {path}")
    if not Path(path).exists():
        print("  文件不存在")
        return
    
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print(f"  总行数: {len(lines)}")
        
        if len(lines) > 0:
            data = json.loads(lines[0])
            has_traj = 'trajectory' in data
            traj_len = len(data.get('trajectory', [])) if has_traj else 0
            print(f"  有trajectory字段: {has_traj}")
            print(f"  轨迹点数: {traj_len}")
            if traj_len > 0:
                print(f"  第一个轨迹点: {data['trajectory'][0]}")
            else:
                print("  轨迹为空")

check_file("logs_v2/proto_main_eval/gs_proto_driven_test.jsonl")
check_file("logs_v2/proto_main_eval/random_proto_driven_test.jsonl")

