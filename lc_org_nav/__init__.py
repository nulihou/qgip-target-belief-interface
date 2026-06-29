"""
LC-ORGNav: Language-Conditioned Object-Relation Graph Navigation

A state-of-the-art system for language-conditioned goal selection in
autonomous driving scenarios using advanced graph neural networks.
"""

__version__ = "1.0.0"
__author__ = "Your Name"

# Basic imports
try:
    from .config import TrainConfig
    from .dataset import GoalSelectionDataset
    from .model import LCORGNet
    from .trainer import GoalSelectorTrainer
    
    # Advanced imports
    from .config_advanced import (
        AdvancedTrainConfig,
        BaselineConfig,
        get_config,
        CONFIG_REGISTRY,
    )
    from .model_advanced import LCORGNetAdvanced
    from .trainer_advanced import AdvancedTrainer
    from .losses import CombinedLoss
    from .metrics import MetricsCalculator
    from .inference import InferenceEngine, load_model_for_inference
    from .visualization import TrainingVisualizer, SceneGraphVisualizer
    from .data_augmentation import (
        GraphAugmentation,
        HardNegativeSampler,
        SyntheticSceneGenerator,
    )
except (ImportError, OSError) as e:
    # Allow partial imports for tools that don't need full dependencies (e.g. data collection without torch)
    pass

# GTX 1660S optimized configs
try:
    from .config_gtx1660s import GTX1660SConfig, GTX1660SUltraLightConfig
except ImportError:
    pass  # Optional module

__all__ = [
    # Version
    "__version__",
    "__author__",
    
    # Basic (might be unavailable if import failed)
    "TrainConfig",
    "GoalSelectionDataset",
    "LCORGNet",
    "GoalSelectorTrainer",
    
    # Advanced
    "AdvancedTrainConfig",
    "BaselineConfig",
    "get_config",
    "CONFIG_REGISTRY",
    "LCORGNetAdvanced",
    "AdvancedTrainer",
    "CombinedLoss",
    "MetricsCalculator",
    "InferenceEngine",
    "load_model_for_inference",
    "TrainingVisualizer",
    "SceneGraphVisualizer",
    "GraphAugmentation",
    "HardNegativeSampler",
    "SyntheticSceneGenerator",
]
