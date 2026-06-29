"""
演示脚本：自然语言指令 → Query Schema → Binding Mask → 目标选择

目标：验证整个流程
1. 输入："Follow the red truck"
2. 解析为 Query Schema
3. 生成 binding_mask
4. 在仿真里跟随选中的目标

这是第一步的最短闭环验证。
"""

import sys
import os
import numpy as np
from typing import Dict, Any, List

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from lc_org_nav.query_schema import QuerySchema
from lc_org_nav.nl_parser import NaturalLanguageParser
from lc_org_nav.grounding import BindingMaskGenerator, TrackedObject


def demo_follow_language():
    """演示：自然语言指令到目标选择的完整流程"""
    
    print("=" * 60)
    print("自然语言指令 → Query Schema → Binding Mask → 目标选择")
    print("=" * 60)
    print()
    
    # 步骤 1: 解析自然语言
    parser = NaturalLanguageParser()
    
    test_instructions = [
        "Follow the red truck",
        "Follow the white SUV",
        "Follow the car in front",
    ]
    
    for instruction in test_instructions:
        print(f"【指令】: '{instruction}'")
        print("-" * 60)
        
        # 解析为 Schema
        schema = parser.parse(instruction)
        print(f"【Schema】:")
        print(QuerySchema.to_json(schema))
        print(f"【摘要】: {QuerySchema.get_attributes_summary(schema)}")
        print(f"【有效】: {QuerySchema.is_valid(schema)}")
        print()
        
        # 步骤 2: 创建模拟的 tracked objects
        ego_pos = np.array([0.0, 0.0])
        ego_heading = 0.0
        
        objects = create_mock_tracked_objects()
        
        # 步骤 3: 生成 binding_mask
        generator = BindingMaskGenerator(ego_position=ego_pos, ego_heading=ego_heading)
        candidate_indices = list(range(len(objects)))  # 所有对象都是候选
        
        binding_mask, metadata = generator.generate(
            schema, objects, candidate_indices
        )
        
        print(f"【Binding Mask】:")
        print(f"  候选数量: {metadata['num_candidates']}")
        print(f"  匹配数量: {metadata['num_matches']}")
        print(f"  置信度: {metadata['confidence']:.2f}")
        print(f"  Mask: {binding_mask}")
        print()
        
        # 步骤 4: 显示匹配的对象
        print(f"【匹配的对象】:")
        matched_indices = np.where(binding_mask)[0]
        if len(matched_indices) > 0:
            for idx in matched_indices:
                obj = objects[candidate_indices[idx]]
                print(f"  - Track ID {obj.track_id}: {obj.vehicle_class} at {obj.position[:2]}")
        else:
            print("  (无匹配对象)")
        print()
        
        # 步骤 5: 模拟目标选择（使用 binding_mask 过滤候选）
        if binding_mask.sum() > 0:
            # 这里应该接入实际的 GNN 模型
            # 当前只是演示：选择第一个匹配的对象
            selected_idx = matched_indices[0]
            selected_obj = objects[candidate_indices[selected_idx]]
            print(f"【选中的目标】:")
            print(f"  Track ID: {selected_obj.track_id}")
            print(f"  类别: {selected_obj.vehicle_class}")
            print(f"  位置: {selected_obj.position[:2]}")
        else:
            print(f"【选中的目标】: (无匹配，无法选择)")
        
        print()
        print("=" * 60)
        print()


def create_mock_tracked_objects() -> List[TrackedObject]:
    """创建模拟的跟踪对象（用于演示）"""
    objects = [
        TrackedObject(
            track_id=1,
            position=np.array([15.0, 0.0]),  # 正前方
            vehicle_class="truck",
            heading=0.0,
        ),
        TrackedObject(
            track_id=2,
            position=np.array([12.0, -2.5]),  # 右侧前方
            vehicle_class="car",
            heading=0.0,
        ),
        TrackedObject(
            track_id=3,
            position=np.array([12.0, 2.5]),  # 左侧前方
            vehicle_class="suv",
            heading=0.0,
        ),
        TrackedObject(
            track_id=4,
            position=np.array([18.0, 0.0]),  # 正前方（更远）
            vehicle_class="truck",
            heading=0.0,
        ),
        TrackedObject(
            track_id=5,
            position=np.array([-5.0, 0.0]),  # 后方
            vehicle_class="car",
            heading=np.pi,
        ),
    ]
    return objects


def test_audit_scenarios():
    """测试审计场景：验证系统对指令切换的响应"""
    print("=" * 60)
    print("审计测试：指令切换验证")
    print("=" * 60)
    print()
    
    parser = NaturalLanguageParser()
    objects = create_mock_tracked_objects()
    ego_pos = np.array([0.0, 0.0])
    ego_heading = 0.0
    generator = BindingMaskGenerator(ego_pos, ego_heading)
    
    # 场景 1: "Follow the red truck"
    instruction1 = "Follow the red truck"
    schema1 = parser.parse(instruction1)
    mask1, meta1 = generator.generate(schema1, objects)
    
    print(f"【场景1】: '{instruction1}'")
    print(f"匹配数量: {meta1['num_matches']}")
    matched1 = [objects[i].track_id for i in np.where(mask1)[0]]
    print(f"匹配的 Track IDs: {matched1}")
    print()
    
    # 场景 2: "Follow the white SUV"（应该切换目标）
    instruction2 = "Follow the white SUV"
    schema2 = parser.parse(instruction2)
    mask2, meta2 = generator.generate(schema2, objects)
    
    print(f"【场景2】: '{instruction2}'")
    print(f"匹配数量: {meta2['num_matches']}")
    matched2 = [objects[i].track_id for i in np.where(mask2)[0]]
    print(f"匹配的 Track IDs: {matched2}")
    print()
    
    # 验证切换
    if set(matched1) != set(matched2):
        print("[PASS] 审计通过：指令切换导致目标切换")
    else:
        print("[WARN] 审计警告：指令切换但目标未切换")
    print()
    
    # 场景 3: No-Query（应该性能显著变差）
    print(f"【场景3】: No-Query（无查询条件）")
    schema_empty = QuerySchema.create_empty()
    mask_empty, meta_empty = generator.generate(schema_empty, objects)
    print(f"匹配数量: {meta_empty['num_matches']} (应该是全部，因为没有过滤条件)")
    print(f"置信度: {meta_empty['confidence']:.2f}")
    print()
    
    if meta_empty['num_matches'] == len(objects):
        print("[PASS] 审计通过：No-Query 时所有对象都匹配（无过滤）")
    else:
        print("[WARN] 审计警告：No-Query 时仍有过滤")
    print()


if __name__ == "__main__":
    # 运行主演示
    demo_follow_language()
    
    # 运行审计测试
    print("\n\n")
    test_audit_scenarios()

