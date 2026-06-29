#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将所有可视化数据文件复制到统一文件夹
"""

import json
import shutil
from pathlib import Path

# 目标文件夹
target_dir = Path("visualization_data")
target_dir.mkdir(exist_ok=True)

# 读取数据文件映射
with open("VISUALIZATION_DATA_COMPLETE.json", "r", encoding="utf-8") as f:
    data = json.load(f)

file_mapping = data["data_file_mapping"]

# 文件列表和说明
files_to_copy = [
    # 主数据文件
    ("VISUALIZATION_DATA_COMPLETE.json", "主数据汇总文件（包含所有数据）"),
    
    # 表1: 离线GS性能分组
    (file_mapping["offline_grouped"], "表1: 离线GS性能分组统计"),
    
    # 表2: Protocol-level目标选择
    (file_mapping["protocol_eval"], "表2: Protocol-level目标选择"),
    
    # 表3: 语义导航性能
    (file_mapping["semantic_navsucc"], "表3: 语义导航性能分析"),
    
    # 表4: Online导航性能
    (file_mapping["online_metrics"], "表4: Online导航性能指标"),
    
    # 表6: Ranking Loss消融实验
    (file_mapping["ablation_comparison"], "表6: Ranking Loss消融实验对比"),
    
    # 表7: 难度分组鲁棒性
    (file_mapping["difficulty_robustness"], "表7: 难度分组鲁棒性分析"),
    
    # 表8: 运行效率
    (file_mapping["runtime_performance"], "表8: 运行效率数据"),
]

# 轨迹数据文件
trajectory_dir = Path(file_mapping["trajectory_eval"])
trajectory_files = [
    "gs_proto_driven.jsonl",
    "random_proto_driven.jsonl",
    "oracle_proto_driven.jsonl"
]

# 复制文件
copied_files = []
failed_files = []

print("="*60)
print("复制可视化数据文件")
print("="*60)

# 复制主数据文件
for file_path, description in files_to_copy:
    src = Path(file_path)
    if src.exists():
        if src.is_file():
            dst = target_dir / src.name
            shutil.copy2(src, dst)
            copied_files.append((dst.name, description))
            print(f"[OK] {src.name} -> {description}")
        elif src.is_dir():
            # 如果是目录，创建子目录并复制内容
            dst_dir = target_dir / src.name
            dst_dir.mkdir(exist_ok=True)
            for item in src.iterdir():
                if item.is_file():
                    shutil.copy2(item, dst_dir / item.name)
            copied_files.append((src.name, description + " (目录)"))
            print(f"[OK] {src.name}/ -> {description} (目录)")
    else:
        failed_files.append((file_path, description))
        print(f"[FAIL] {file_path} -> 文件不存在")

# 复制轨迹数据文件
trajectory_target_dir = target_dir / "trajectory_eval"
trajectory_target_dir.mkdir(exist_ok=True)

for traj_file in trajectory_files:
    src = trajectory_dir / traj_file
    if src.exists():
        dst = trajectory_target_dir / traj_file
        shutil.copy2(src, dst)
        copied_files.append((f"trajectory_eval/{traj_file}", f"轨迹数据: {traj_file}"))
        print(f"[OK] trajectory_eval/{traj_file} -> 轨迹数据")
    else:
        failed_files.append((str(src), f"轨迹数据: {traj_file}"))
        print(f"[FAIL] {src} -> 文件不存在")

# 创建索引文件
index_content = """# 可视化数据文件索引

**生成日期**: 2025-11-23
**说明**: 本文件夹包含所有用于可视化的原始数据文件

---

## 📁 文件列表

"""
for filename, description in copied_files:
    index_content += f"### {filename}\n"
    index_content += f"- **说明**: {description}\n\n"

if failed_files:
    index_content += "\n---\n\n## ⚠️ 未找到的文件\n\n"
    for file_path, description in failed_files:
        index_content += f"- {file_path}: {description}\n"

index_content += """

---

## 📊 数据文件对应关系

| 数据表 | 对应文件 |
|--------|----------|
| 表1: 离线GS性能分组 | `offline_grouped_analysis.json` |
| 表2: Protocol-level目标选择 | `proto_eval_summary.json` |
| 表3: 语义导航性能 | `semantic_navsucc_analysis.md` |
| 表4: Online导航性能 | `MAIN_ONLINE_TABLE.md` |
| 表5: 2×2列联表 | `semantic_navsucc_analysis.md` (从表3数据计算) |
| 表6: Ranking Loss消融 | `ablation/full_vs_no_rank_30ep_comparison.json` |
| 表7: 难度分组鲁棒性 | `difficulty_robustness_analysis.json` |
| 表8: 运行效率 | `runtime_performance.json` |
| 轨迹数据 | `trajectory_eval/*.jsonl` |

---

## 📝 使用说明

1. **主数据文件**: `VISUALIZATION_DATA_COMPLETE.json` 包含所有数据的汇总
2. **原始数据文件**: 各个JSON/MD文件包含详细的原始数据
3. **轨迹数据**: `trajectory_eval/` 目录包含完整的轨迹数据（用于轨迹图）

---

## 🔄 数据更新

如果实验数据有更新，需要：
1. 更新原始数据文件
2. 重新运行 `scripts/visualization/copy_visualization_data.py` 复制最新文件
3. 更新 `VISUALIZATION_DATA_COMPLETE.json`（如果需要）

---

**总文件数**: """ + str(len(copied_files)) + """
"""

with open(target_dir / "README.md", "w", encoding="utf-8") as f:
    f.write(index_content)

print("\n" + "="*60)
print(f"[完成] 已复制 {len(copied_files)} 个文件到 {target_dir}")
if failed_files:
    print(f"[警告] {len(failed_files)} 个文件未找到")
print(f"[索引] 已创建 README.md 索引文件")
print("="*60)

