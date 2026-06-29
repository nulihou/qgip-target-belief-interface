#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""运行 Step 2 验证并保存结果"""

import sys
import os
import traceback
from datetime import datetime

# 添加项目根目录
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 结果文件
result_file = os.path.join(_project_root, "step2_verification_result.txt")

with open(result_file, "w", encoding="utf-8") as f:
    f.write("=" * 60 + "\n")
    f.write("Step 2 验证测试结果\n")
    f.write(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("=" * 60 + "\n\n")
    
    # 测试 1: 模块导入
    f.write("[1/5] 测试模块导入...\n")
    try:
        from lc_org_nav.nl_parser import NaturalLanguageParser
        from lc_org_nav.grounding import BindingMaskGenerator, TrackedObject
        from lc_org_nav.online_nav.carla_grounding import carla_vehicle_to_tracked_object
        from lc_org_nav.online_nav.target_select import apply_binding_mask
        f.write("✅ OK - 所有模块导入成功\n\n")
    except Exception as e:
        f.write(f"❌ FAIL - 模块导入失败: {e}\n")
        f.write(traceback.format_exc() + "\n\n")
        sys.exit(1)
    
    # 测试 2: 自然语言解析
    f.write("[2/5] 测试自然语言解析...\n")
    try:
        parser = NaturalLanguageParser()
        schema = parser.parse("Follow the red truck")
        # 验证 schema 是否有效
        is_valid = schema is not None and schema.get("mission") is not None
        if is_valid:
            f.write("✅ OK - 解析成功\n")
            f.write(f"   Schema: mission={schema.get('mission')}\n")
            f.write(f"   class={schema.get('bindings', {}).get('target_object', {}).get('attributes', {}).get('class')}\n")
            f.write(f"   color={schema.get('bindings', {}).get('target_object', {}).get('attributes', {}).get('color')}\n\n")
        else:
            f.write(f"❌ FAIL - 解析失败: {error}\n\n")
    except Exception as e:
        f.write(f"❌ FAIL - 解析测试失败: {e}\n")
        f.write(traceback.format_exc() + "\n\n")
    
    # 测试 3: binding_mask 生成
    f.write("[3/5] 测试 binding_mask 生成...\n")
    try:
        import numpy as np
        from unittest.mock import Mock
        
        red_truck_actor = Mock()
        red_truck_actor.id = 1
        red_truck_actor.attributes = {'color': '255,0,0'}
        red_truck_actor.type_id = "vehicle.freightliner.cascadia"
        
        obj = carla_vehicle_to_tracked_object(red_truck_actor)
        obj.position = np.array([15.0, 0.0, 0.5])
        
        generator = BindingMaskGenerator(ego_position=np.array([0.0, 0.0]), ego_heading=0.0)
        mask, meta = generator.generate(schema, [obj])
        
        f.write("✅ OK - Binding mask 生成成功\n")
        f.write(f"   Mask: {mask.tolist()}\n")
        f.write(f"   匹配数量: {meta['num_matches']}\n")
        f.write(f"   置信度: {meta['confidence']:.2f}\n\n")
    except Exception as e:
        f.write(f"❌ FAIL - Binding mask 测试失败: {e}\n")
        f.write(traceback.format_exc() + "\n\n")
    
    # 测试 4: CARLA 连接
    f.write("[4/5] 测试 CARLA 连接...\n")
    try:
        import carla
        client = carla.Client("localhost", 2000)
        client.set_timeout(5.0)
        world = client.get_world()
        f.write("✅ OK - CARLA 连接成功\n")
        f.write(f"   当前地图: {world.get_map().name}\n\n")
    except Exception as e:
        f.write(f"❌ FAIL - CARLA 连接失败: {e}\n")
        f.write("   请确保 CARLA 已启动\n\n")
    
    # 测试 5: 模型加载
    f.write("[5/5] 测试模型加载...\n")
    checkpoint_paths = [
        "outputs_v2/multitask_mixed_v2_online_multi_rank/lambda_rel0.1_geom0.02/best_lc_org_mtl_mixed.pt",
        "outputs_v2/multitask_mixed_v2_online_multi_rank/seed_42/best_lc_org_mtl_mixed.pt",
    ]
    
    checkpoint_found = False
    for checkpoint_path in checkpoint_paths:
        full_path = os.path.join(_project_root, checkpoint_path)
        if os.path.exists(full_path):
            try:
                import torch
                from lc_org_nav.online_nav.gs_loader import load_gs_model
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                f.write(f"   找到 checkpoint: {checkpoint_path}\n")
                f.write(f"   使用设备: {device}\n")
                model = load_gs_model(full_path, device)
                f.write("✅ OK - 模型加载成功\n\n")
                checkpoint_found = True
                break
            except Exception as e:
                f.write(f"⚠️  WARN - 模型加载失败 ({checkpoint_path}): {e}\n")
                continue
    
    if not checkpoint_found:
        f.write("⚠️  SKIP - 未找到可用的 checkpoint\n\n")
    
    f.write("=" * 60 + "\n")
    f.write("测试完成！\n")
    f.write("=" * 60 + "\n")

print(f"验证完成！结果已保存到: {result_file}")

