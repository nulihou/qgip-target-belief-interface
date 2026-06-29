# QGIP Target-Belief Interface

Code and lightweight artifacts for an auditable target-belief interface for vehicle following under object-list ambiguity.

This repository contains the implementation and reproducibility materials around the QGIP-Net / LLC-POP/NIS-MPC stack. The project studies how a controller-facing leader belief can be selected, maintained, diagnosed, and converted into a conservative command when object-list detections contain false positives, ID switches, dropouts, delays, or inconsistent measurements.

## Scope

The repository is scoped to a simulation-first and low-speed ROS2 validation workflow. It does not claim full-scale road validation, raw-sensor robustness, or a formal autonomous-driving safety proof.

The core interface exposes:

- selected leader identity and confidence;
- POP/NIS belief state with TRACK, GHOST, DEGRADED, and LOST modes;
- MPC / safety-controller diagnostics;
- safe command output for replay, shadow mode, or low-speed robot trials.

## Repository Layout

```text
lc_org_nav/              Core Python package for graph-based leader selection, tracking, and control utilities
scripts/                 Training, evaluation, visualization, and benchmark scripts
analysis_scripts/        Paper-scale analysis, figure, audit, and summary scripts
ros2_deployment/         ROS2 / Jetson Nano preflight and low-speed robot validation stack
paper_artifacts/         Lightweight source tables and source-data artifacts
paper_figures/           Figure-generation scripts and compact rendered figures
docs/                    System and methodology notes
visualization/           Example visualization outputs
```

Large generated artifacts are intentionally excluded, including CARLA datasets, model checkpoints, manuscript submission packages, raw rosbags, temporary build directories, and large TIFF/PDF archives.

## Environment

The historical CARLA experiments used Python with PyTorch/PyG and CARLA 0.9.x. The lightweight environment file is provided as:

```bash
conda env create -f environment.yml
conda activate lc_org_nav
```

Some scripts depend on local CARLA, ROS2, or paper-artifact paths and may need path updates before being run on a new machine.

## Basic Evaluation Entry Points

```bash
python run_final_benchmark_300.py
python analyze_metrics.py
python scripts/eval/run_batch_stats.py --num-episodes 5
```

These commands assume the expected CARLA runtime, datasets, and checkpoints are available locally. Those large files are not stored in this Git repository.

## ROS2 / Robot Validation

The ROS2 validation materials are under `ros2_deployment/`. Start with:

```bash
cd ros2_deployment
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py --show-args
```

Recommended low-speed validation order:

1. shadow-mode topic and command-chain preflight;
2. suspended-wheel preflight, if available;
3. low-speed on-ground straight following;
4. short dropout;
5. sustained dropout / LOST safe-stop trial;
6. optional adjacent distractor or ID-switch trials.

See `ros2_deployment/JETSON_NANO_REAL_ROBOT_REPRODUCTION.zh-CN.md`, `ros2_deployment/real_robot_trials_matrix.csv`, and `ros2_deployment/pre_real_robot_checklist.md`.

## Data And Checkpoints

This repository is a code and lightweight-artifact release. It does not include:

- raw CARLA `.npz` datasets;
- trained `.pt` / `.pth` checkpoints;
- large generated figures;
- manuscript submission archives;
- raw ROS2 bags or robot video.

If you reproduce the experiments, place local-only assets outside the repository or in ignored directories such as `data/`, `checkpoints/`, `outputs/`, or `runs/`.

## Citation

If you use this code, please cite the associated manuscript once available.
