"""
最小闭环跟随测试（Task 7）

在 CARLA 中实现最小闭环跟随，验证自然语言指令 → binding_mask → 目标选择 → 跟随的完整流程
"""

import os
import sys
import json
import argparse
import numpy as np
import torch
from typing import Dict, Any, List, Optional
from pathlib import Path

# 添加项目根目录到路径
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# CARLA Python API 路径
_carla_python_api_paths = [
    os.environ.get("CARLA_PYTHON_API_PATH"),
    "E:/carla/WindowsNoEditor/PythonAPI",
    "/opt/carla/PythonAPI",
]

for path in _carla_python_api_paths:
    if path and os.path.exists(path):
        if path not in sys.path:
            sys.path.insert(0, path)
        break

try:
    import carla
    CARLA_AVAILABLE = True
except ImportError:
    CARLA_AVAILABLE = False
    print("[WARNING] CARLA not available. Running in mock mode.")
    carla = None

from lc_org_nav.nl_parser import NaturalLanguageParser
from lc_org_nav.grounding import BindingMaskGenerator
from lc_org_nav.online_nav.carla_grounding import (
    build_tracked_objects_from_scene,
    carla_vehicle_to_tracked_object,
)
from lc_org_nav.online_nav.target_select import select_target_gs, apply_binding_mask
from lc_org_nav.model import LCORGNet
from lc_org_nav.online_nav.gs_loader import load_gs_model


def setup_simple_scene(
    world: Any,
    client: Any,
    num_candidates: int = 3,
) -> Dict[str, Any]:
    """
    设置简单场景：直路 + 两台不同颜色/类型车
    
    Returns:
        包含 ego_vehicle, target_vehicle, candidate_vehicles 的字典
    """
    if not CARLA_AVAILABLE:
        return {}
    
    blueprint_library = world.get_blueprint_library()
    
    # 清理现有车辆
    all_actors = world.get_actors()
    vehicles_to_destroy = [actor for actor in all_actors if actor.type_id.startswith('vehicle.')]
    for vehicle in vehicles_to_destroy:
        try:
            vehicle.destroy()
        except:
            pass
    
    for _ in range(20):
        world.tick()
    
    # Spawn ego vehicle
    ego_bp = blueprint_library.filter("vehicle.tesla.model3")[0]
    ego_bp.set_attribute("role_name", "ego")
    
    # Spawn target vehicle（红色卡车）
    target_bp = blueprint_library.filter("vehicle.*truck*")
    if not target_bp:
        target_bp = blueprint_library.filter("vehicle.*")
    target_bp = target_bp[0]
    if target_bp.has_attribute("color"):
        # 设置为红色
        red_colors = [c for c in target_bp.get_attribute("color").recommended_values if "255,0,0" in c or "red" in c.lower()]
        if red_colors:
            target_bp.set_attribute("color", red_colors[0])
        else:
            target_bp.set_attribute("color", "255,0,0")
    target_bp.set_attribute("role_name", "target_red_truck")
    
    # Spawn candidate vehicle（白色SUV）
    candidate_bp = blueprint_library.filter("vehicle.*")
    candidate_bp = [bp for bp in candidate_bp if "suv" in bp.id.lower() or "jeep" in bp.id.lower()]
    if not candidate_bp:
        candidate_bp = blueprint_library.filter("vehicle.*")
    candidate_bp = candidate_bp[0]
    if candidate_bp.has_attribute("color"):
        # 设置为白色
        white_colors = [c for c in candidate_bp.get_attribute("color").recommended_values if "255,255,255" in c or "white" in c.lower()]
        if white_colors:
            candidate_bp.set_attribute("color", white_colors[0])
        else:
            candidate_bp.set_attribute("color", "255,255,255")
    candidate_bp.set_attribute("role_name", "candidate_white_suv")
    
    # 获取 spawn points
    spawn_points = world.get_map().get_spawn_points()
    if len(spawn_points) < 3:
        raise RuntimeError("Not enough spawn points")
    
    # Spawn vehicles
    ego_vehicle = world.spawn_actor(ego_bp, spawn_points[0])
    target_vehicle = world.spawn_actor(target_bp, spawn_points[1])
    candidate_vehicle = world.spawn_actor(candidate_bp, spawn_points[2])
    
    # 设置车辆为静态（简化测试）
    for vehicle in [target_vehicle, candidate_vehicle]:
        vehicle.set_autopilot(False)
        zero_control = carla.VehicleControl(
            throttle=0.0, steer=0.0, brake=1.0,
            hand_brake=False, reverse=False, manual_gear_shift=False
        )
        vehicle.apply_control(zero_control)
    
    return {
        "ego_vehicle": ego_vehicle,
        "target_vehicle": target_vehicle,
        "candidate_vehicles": [candidate_vehicle],
    }


def run_follow_test(
    instruction: str,
    world: Any,
    ego_vehicle: Any,
    target_vehicle: Any,
    candidate_vehicles: List[Any],
    model: Any,
    device: torch.device,
    max_steps: int = 100,
) -> Dict[str, Any]:
    """
    运行跟随测试
    
    Args:
        instruction: 自然语言指令，如 "Follow the red truck"
        world: CARLA world
        ego_vehicle: 自车
        target_vehicle: 目标车辆
        candidate_vehicles: 候选车辆列表
        model: GNN 模型
        device: 设备
        max_steps: 最大步数
    
    Returns:
        测试结果字典
    """
    # 1. 解析自然语言指令
    parser = NaturalLanguageParser()
    schema = parser.parse(instruction)
    
    print(f"[Step 1] 解析指令: '{instruction}'")
    print(f"  Schema: {schema}")
    print()
    
    # 2. 构建 tracked objects
    all_vehicles = [target_vehicle] + candidate_vehicles
    tracked_objects, track_id_to_node_idx = build_tracked_objects_from_scene(
        world, ego_vehicle, all_vehicles
    )
    
    print(f"[Step 2] 构建 TrackedObjects")
    print(f"  找到 {len(tracked_objects)} 个车辆")
    for obj in tracked_objects:
        print(f"    - Track {obj.track_id}: {obj.vehicle_class} at {obj.position[:2]}")
    print()
    
    # 3. 生成 binding_mask
    ego_transform = ego_vehicle.get_transform()
    ego_position = np.array([ego_transform.location.x, ego_transform.location.y])
    ego_heading = np.radians(ego_transform.rotation.yaw)
    
    generator = BindingMaskGenerator(ego_position, ego_heading)
    binding_mask, binding_metadata = generator.generate(
        schema, tracked_objects, image=None  # 暂时不使用图像
    )
    
    print(f"[Step 3] 生成 Binding Mask")
    print(f"  Binding mask: {binding_mask}")
    print(f"  匹配数量: {binding_metadata['num_matches']}/{binding_metadata['num_candidates']}")
    print(f"  置信度: {binding_metadata['confidence']:.2f}")
    if binding_metadata.get('degradation_applied'):
        print(f"  ⚠️  降级策略已应用")
    print()
    
    # 4. 构建图（简化版，使用 protocol graph 或实时构建）
    # 这里我们使用一个简化的图结构
    from lc_org_nav.online_nav.graph_builder import build_graph_from_scene
    
    graph = build_graph_from_scene(
        world, ego_vehicle, target_vehicle, candidate_vehicles
    )
    
    if graph is None:
        return {"error": "Failed to build graph"}
    
    # 5. 应用 binding_mask 并选择目标
    # 将 binding_mask 转换为与 graph 节点顺序对应
    # 注意：需要确保 binding_mask 的索引与 graph 的节点顺序一致
    protocol_candidate_mask = graph["candidate_mask"]
    
    # 构建 binding_mask（与 graph 节点顺序对应）
    # 这里简化处理：假设 tracked_objects 的顺序与 graph 节点顺序一致
    if len(tracked_objects) == len(protocol_candidate_mask):
        binding_mask_tensor = torch.from_numpy(binding_mask).to(device)
    else:
        # 如果数量不匹配，使用全 1（不应用 binding_mask）
        binding_mask_tensor = None
        print(f"  ⚠️  TrackedObjects 数量 ({len(tracked_objects)}) 与 graph 节点数 ({len(protocol_candidate_mask)}) 不匹配，跳过 binding_mask")
    
    # 选择目标
    chosen_idx, gs_correct, gs_metrics = select_target_gs(
        graph, model, device, debug=True, binding_mask=binding_mask_tensor
    )
    
    print(f"[Step 4] 目标选择")
    print(f"  选中的索引: {chosen_idx}")
    print(f"  GS@1 正确: {gs_correct}")
    print(f"  Binding 应用: {gs_metrics.get('binding_applied', False)}")
    print()
    
    # 6. 记录日志
    log_entry = {
        "instruction": instruction,
        "schema": schema,
        "tracked_objects": [obj.to_dict() for obj in tracked_objects],
        "binding_mask": binding_mask.tolist() if isinstance(binding_mask, np.ndarray) else binding_mask,
        "binding_metadata": binding_metadata,
        "chosen_idx": int(chosen_idx),
        "gs_correct": bool(gs_correct),
        "gs_metrics": {k: (v.tolist() if isinstance(v, (np.ndarray, torch.Tensor)) else v) 
                       for k, v in gs_metrics.items()},
    }
    
    return {
        "success": True,
        "log_entry": log_entry,
    }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="最小闭环跟随测试")
    parser.add_argument("--instruction", type=str, default="Follow the red truck",
                       help="自然语言指令")
    parser.add_argument("--checkpoint", type=str, 
                       default="outputs_v2/multitask_mixed_v2_online_multi_rank/seed_42/best_lc_org_mtl_mixed.pt",
                       help="模型 checkpoint 路径")
    parser.add_argument("--host", type=str, default="localhost", help="CARLA 服务器地址")
    parser.add_argument("--port", type=int, default=2000, help="CARLA 服务器端口")
    parser.add_argument("--town", type=str, default="Town01", help="CARLA 城镇")
    parser.add_argument("--output", type=str, default="logs_v2/demo_follow_carla.jsonl",
                       help="输出日志路径")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("最小闭环跟随测试（Task 7）")
    print("=" * 60)
    print()
    
    # 连接 CARLA
    if CARLA_AVAILABLE:
        try:
            client = carla.Client(args.host, args.port)
            client.set_timeout(10.0)
            world = client.get_world()
            world = client.load_world(args.town)
            print(f"[Setup] 连接到 CARLA: {args.host}:{args.port}, Town: {args.town}")
        except Exception as e:
            print(f"[ERROR] 无法连接到 CARLA: {e}")
            return
    else:
        print("[WARNING] CARLA 不可用，运行在 mock 模式")
        return
    
    # 加载模型
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Setup] 设备: {device}")
    
    try:
        model = load_gs_model(args.checkpoint, device)
        print(f"[Setup] 模型加载成功: {args.checkpoint}")
    except Exception as e:
        print(f"[ERROR] 模型加载失败: {e}")
        return
    
    # 设置场景
    try:
        scene = setup_simple_scene(world, client)
        ego_vehicle = scene["ego_vehicle"]
        target_vehicle = scene["target_vehicle"]
        candidate_vehicles = scene["candidate_vehicles"]
        print(f"[Setup] 场景设置完成")
    except Exception as e:
        print(f"[ERROR] 场景设置失败: {e}")
        return
    
    print()
    
    # 运行测试
    result = run_follow_test(
        args.instruction,
        world,
        ego_vehicle,
        target_vehicle,
        candidate_vehicles,
        model,
        device,
    )
    
    if result.get("success"):
        print("=" * 60)
        print("✅ 测试完成")
        print("=" * 60)
        
        # 保存日志
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(result["log_entry"], ensure_ascii=False) + "\n")
        
        print(f"日志已保存到: {output_path}")
    else:
        print(f"[ERROR] 测试失败: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()

