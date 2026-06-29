#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建论文归档目录结构并复制最终文件
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "paper_artifacts_v1"

# 目录结构定义
DIRS = [
    "repro",
    "main/logs",
    "main/seeds",
    "main/checks",
    "main/tables",
    "main/figs",
    "main/figs/diagnosis_2x2",
    "oracle/tables",
    "oracle/reports",
    "oracle/figs",
    "semantic/semcrit/data",
    "semantic/semcrit/protocols",
    "semantic/semcrit/logs",
    "semantic/semcrit/tables",
    "semantic/semcrit/reports",
    "semantic/semcrit/checks",
    "semantic/queryflip/data",
    "semantic/queryflip/protocols",
    "semantic/queryflip/models/finetune_B",
    "semantic/queryflip/results",
    "semantic/queryflip/tables",
    "semantic/queryflip/reports",
]

def create_dirs():
    """创建目录结构"""
    print("Creating directory structure...")
    for dir_path in DIRS:
        full_path = ARTIFACTS_DIR / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"  [OK] {dir_path}")
    print("Directory structure created successfully\n")

if __name__ == "__main__":
    create_dirs()
