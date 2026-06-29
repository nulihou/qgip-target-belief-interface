#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
随机种子管理器（Step 2.1）

固定并记录所有随机源：
- carla_seed
- traffic_manager_seed
- python random/np/torch seed
- 场景id（JSON中已有）
"""

import random
import numpy as np
import torch
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict


@dataclass
class RandomSeedConfig:
    """随机种子配置"""
    scene_id: int
    run_id: int  # 第几次运行（1-based，用于30×R扩展）
    carla_seed: int
    traffic_manager_seed: int
    python_random_seed: int
    numpy_seed: int
    torch_seed: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'RandomSeedConfig':
        return cls(**d)


class RandomSeedManager:
    """随机种子管理器"""
    
    def __init__(
        self,
        base_seed: int = 42,
        num_runs_per_scene: int = 5
    ):
        """
        初始化随机种子管理器
        
        Args:
            base_seed: 基础随机种子
            num_runs_per_scene: 每个场景运行次数（R=5）
        """
        self.base_seed = base_seed
        self.num_runs_per_scene = num_runs_per_scene
        self.seed_configs: List[RandomSeedConfig] = []
    
    def generate_seed_config(
        self,
        scene_id: int,
        run_id: int
    ) -> RandomSeedConfig:
        """
        为特定场景和运行生成随机种子配置
        
        Args:
            scene_id: 场景ID（0-based）
            run_id: 运行ID（1-based，1到R）
        
        Returns:
            随机种子配置
        """
        # 使用确定性方式生成种子
        # 公式：seed = base_seed + scene_id * 1000 + run_id * 100
        seed_offset = scene_id * 1000 + run_id * 100
        
        config = RandomSeedConfig(
            scene_id=scene_id,
            run_id=run_id,
            carla_seed=self.base_seed + seed_offset + 1,
            traffic_manager_seed=self.base_seed + seed_offset + 2,
            python_random_seed=self.base_seed + seed_offset + 3,
            numpy_seed=self.base_seed + seed_offset + 4,
            torch_seed=self.base_seed + seed_offset + 5,
        )
        
        self.seed_configs.append(config)
        return config
    
    def apply_seed_config(self, config: RandomSeedConfig):
        """
        应用随机种子配置
        
        Args:
            config: 随机种子配置
        """
        # Python random
        random.seed(config.python_random_seed)
        
        # NumPy
        np.random.seed(config.numpy_seed)
        
        # PyTorch
        torch.manual_seed(config.torch_seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(config.torch_seed)
    
    def generate_all_configs(
        self,
        num_scenes: int = 30
    ) -> List[RandomSeedConfig]:
        """
        为所有场景和运行生成随机种子配置
        
        Args:
            num_scenes: 场景数量（默认30）
        
        Returns:
            所有配置列表
        """
        configs = []
        for scene_id in range(num_scenes):
            for run_id in range(1, self.num_runs_per_scene + 1):
                config = self.generate_seed_config(scene_id, run_id)
                configs.append(config)
        return configs
    
    def save_configs(self, output_path: str):
        """
        保存所有配置到JSON文件
        
        Args:
            output_path: 输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        configs_dict = {
            "base_seed": self.base_seed,
            "num_runs_per_scene": self.num_runs_per_scene,
            "configs": [config.to_dict() for config in self.seed_configs]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(configs_dict, f, indent=2, ensure_ascii=False)
    
    def load_configs(self, input_path: str):
        """
        从JSON文件加载配置
        
        Args:
            input_path: 输入文件路径
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Config file not found: {input_path}")
        
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.base_seed = data.get("base_seed", 42)
        self.num_runs_per_scene = data.get("num_runs_per_scene", 5)
        self.seed_configs = [
            RandomSeedConfig.from_dict(d) for d in data.get("configs", [])
        ]
    
    def get_config(
        self,
        scene_id: int,
        run_id: int
    ) -> Optional[RandomSeedConfig]:
        """
        获取特定场景和运行的配置
        
        Args:
            scene_id: 场景ID
            run_id: 运行ID
        
        Returns:
            配置对象，如果不存在则返回None
        """
        for config in self.seed_configs:
            if config.scene_id == scene_id and config.run_id == run_id:
                return config
        return None


def create_seed_config_file(
    output_path: str = "configs/random_seeds.json",
    num_scenes: int = 30,
    num_runs_per_scene: int = 5,
    base_seed: int = 42
):
    """
    创建随机种子配置文件（便捷函数）
    
    Args:
        output_path: 输出文件路径
        num_scenes: 场景数量
        num_runs_per_scene: 每个场景运行次数
        base_seed: 基础随机种子
    """
    manager = RandomSeedManager(
        base_seed=base_seed,
        num_runs_per_scene=num_runs_per_scene
    )
    manager.generate_all_configs(num_scenes=num_scenes)
    manager.save_configs(output_path)
    print(f"[INFO] 已生成 {len(manager.seed_configs)} 个随机种子配置")
    print(f"[INFO] 保存到: {output_path}")


if __name__ == "__main__":
    # 测试
    manager = RandomSeedManager(base_seed=42, num_runs_per_scene=5)
    configs = manager.generate_all_configs(num_scenes=30)
    print(f"生成了 {len(configs)} 个配置")
    
    # 测试第一个配置
    config = configs[0]
    print(f"\n第一个配置:")
    print(f"  scene_id={config.scene_id}, run_id={config.run_id}")
    print(f"  carla_seed={config.carla_seed}")
    print(f"  python_random_seed={config.python_random_seed}")
    
    # 保存
    manager.save_configs("test_seeds.json")
    
    # 加载
    manager2 = RandomSeedManager()
    manager2.load_configs("test_seeds.json")
    print(f"\n加载了 {len(manager2.seed_configs)} 个配置")

