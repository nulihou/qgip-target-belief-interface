#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查轨迹数据中的起点和终点信息"""

import json
import sys
import io

# Fix encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def check_trajectory_info(file_path):
    print(f"\n检查文件: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        line = f.readline()
        if not line:
            print("  文件为空")
            return
        
        data = json.loads(line)
        traj = data.get('trajectory', [])
        
        print(f"  轨迹总数: {len(traj)}")
        
        if len(traj) > 0:
            print(f"\n  第一个点（起点）:")
            start = traj[0]
            print(f"    step: {start.get('step')}")
            print(f"    x: {start.get('x'):.2f}, y: {start.get('y'):.2f}")
            print(f"    dist: {start.get('dist'):.2f}m")
            print(f"    phase: {start.get('phase')}")
            
            print(f"\n  最后一个点（终点）:")
            end = traj[-1]
            print(f"    step: {end.get('step')}")
            print(f"    x: {end.get('x'):.2f}, y: {end.get('y'):.2f}")
            print(f"    dist: {end.get('dist'):.2f}m")
            print(f"    phase: {end.get('phase')}")
            
            print(f"\n  轨迹点字段: {list(traj[0].keys())}")
            
            # 检查是否有明确的起点/终点标记
            has_start_marker = any('start' in str(k).lower() or 'is_start' in str(k) for k in traj[0].keys())
            has_end_marker = any('end' in str(k).lower() or 'is_end' in str(k) for k in traj[-1].keys())
            
            print(f"\n  是否有起点标记: {has_start_marker}")
            print(f"  是否有终点标记: {has_end_marker}")
            
            # 检查JSONL中的其他字段
            print(f"\n  JSONL中的其他距离信息:")
            print(f"    start_dist: {data.get('start_dist', 'N/A')}")
            print(f"    final_dist: {data.get('final_dist', 'N/A')}")
            print(f"    min_dist: {data.get('min_dist', 'N/A')}")
        else:
            print("  轨迹为空")

check_trajectory_info("logs_v2/proto_main_eval/gs_proto_driven_test.jsonl")

