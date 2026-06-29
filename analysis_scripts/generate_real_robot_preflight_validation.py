#!/usr/bin/env python3
"""Offline validator for the real-robot preflight package."""

from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "03_real_robot"
STACK = REAL / "ros2_qgip_stack"
PKG = STACK / "ros2_qgip_stack"
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
PACKAGE = ROOT / "06_submission_package"

OUT_CSV = SOURCE / "real_robot_preflight_validation.csv"
OUT_REPORT = PACKAGE / "real_robot_preflight_validation_report_20260604.md"


@dataclass
class ValidationRow:
    check_id: str
    layer: str
    requirement: str
    evidence: str
    status: str
    source_artifacts: str
    boundary: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def add(
    rows: list[ValidationRow],
    check_id: str,
    layer: str,
    requirement: str,
    ok: bool,
    evidence: str,
    source_artifacts: str,
    boundary: str,
) -> None:
    rows.append(
        ValidationRow(
            check_id=check_id,
            layer=layer,
            requirement=requirement,
            evidence=evidence,
            status="PASS" if ok else "FAIL",
            source_artifacts=source_artifacts,
            boundary=boundary,
        )
    )


def contains_all(text: str, needles: list[str]) -> tuple[bool, list[str]]:
    missing = [needle for needle in needles if needle not in text]
    return not missing, missing


def compile_ok(paths: list[Path]) -> tuple[bool, str]:
    failed: list[str] = []
    for path in paths:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except Exception as exc:
            failed.append(f"{path.relative_to(ROOT).as_posix()}: {exc}")
    return not failed, "; ".join(failed) if failed else f"{len(paths)} files compile"


def xml_texts(path: Path, tag: str) -> list[str]:
    root = ET.parse(path).getroot()
    return [item.text.strip() for item in root.findall(tag) if item.text]


def csv_has_columns(rows: list[dict[str, str]], columns: list[str]) -> bool:
    return bool(rows) and set(columns).issubset(rows[0].keys())


def yaml_token(text: str, key: str, value: str | None = None) -> bool:
    if value is None:
        return re.search(rf"(^|\n)\s*{re.escape(key)}\s*:", text) is not None
    return re.search(rf"(^|\n)\s*{re.escape(key)}\s*:\s*{re.escape(value)}(\s|$)", text) is not None


def main() -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    PACKAGE.mkdir(parents=True, exist_ok=True)

    package_xml = STACK / "package.xml"
    setup_py = STACK / "setup.py"
    launch_py = STACK / "launch" / "multi_robot_preflight.launch.py"
    config_yaml = STACK / "config" / "multi_robot_profile.yaml"
    readme = STACK / "README.md"
    run_manifest = REAL / "real_robot_run_manifest_template.yaml"
    experiment_params = REAL / "experiment_parameters.yaml"
    rosbag_commands = REAL / "rosbag_commands.md"

    package_xml_text = read_text(package_xml)
    setup_text = read_text(setup_py)
    launch_text = read_text(launch_py)
    config_text = read_text(config_yaml)
    readme_text = read_text(readme)
    run_manifest_text = read_text(run_manifest)
    experiment_text = read_text(experiment_params)
    rosbag_text = read_text(rosbag_commands)
    node_texts = "\n".join(read_text(path) for path in sorted(PKG.glob("*.py")))

    topic_contract = read_csv(REAL / "ros2_topic_contract.csv")
    metric_schema = read_csv(REAL / "real_robot_metric_schema.csv")
    results_header = csv_header(REAL / "real_robot_results_template.csv")
    real_trials = read_csv(REAL / "real_robot_trials_matrix.csv")
    preflight_trials = read_csv(REAL / "preflight_trials_matrix.csv")

    rows: list[ValidationRow] = []

    required_files = [
        package_xml,
        setup_py,
        STACK / "resource" / "ros2_qgip_stack",
        launch_py,
        config_yaml,
        readme,
        PKG / "__init__.py",
        PKG / "json_contract.py",
    ]
    add(
        rows,
        "package_structure_files",
        "package_structure",
        "ROS2 package skeleton has package metadata, resource marker, launch/config files, README, and Python package.",
        all(path.exists() and path.stat().st_size >= 0 for path in required_files),
        "; ".join(f"{path.relative_to(ROOT).as_posix()}={path.exists()}" for path in required_files),
        "03_real_robot/ros2_qgip_stack",
        "File presence does not prove colcon build or runtime node execution.",
    )

    py_paths = [
        *sorted(PKG.glob("*.py")),
        launch_py,
        REAL / "fault_injection_core.py",
        REAL / "pop_nis_kf_core.py",
        REAL / "ros2_ackermann_bridge_skeleton.py",
    ]
    ok, evidence = compile_ok(py_paths)
    add(
        rows,
        "python_sources_compile",
        "package_structure",
        "All ROS2 preflight Python sources and reusable real-robot helpers compile with desktop Python.",
        ok,
        evidence,
        "03_real_robot/**/*.py",
        "Syntax compilation does not import ROS2 modules or execute nodes.",
    )

    xml_name = xml_texts(package_xml, "name")
    xml_version = xml_texts(package_xml, "version")
    build_type = xml_texts(package_xml, "export/build_type")
    add(
        rows,
        "package_xml_identity",
        "package_metadata",
        "package.xml declares the expected package name, version, and ament_python build type.",
        xml_name == ["ros2_qgip_stack"] and xml_version == ["0.1.0"] and build_type == ["ament_python"],
        f"name={xml_name}; version={xml_version}; build_type={build_type}",
        "03_real_robot/ros2_qgip_stack/package.xml",
        "Metadata identity does not prove installability in a ROS2 workspace.",
    )

    exec_deps = set(xml_texts(package_xml, "exec_depend"))
    required_deps = {"geometry_msgs", "nav_msgs", "rclpy", "std_msgs", "tf2_ros"}
    add(
        rows,
        "package_xml_runtime_dependencies",
        "package_metadata",
        "Runtime dependencies cover geometry, odometry, std_msgs JSON payloads, rclpy, and TF lookup.",
        required_deps.issubset(exec_deps),
        f"exec_deps={sorted(exec_deps)}",
        "03_real_robot/ros2_qgip_stack/package.xml",
        "The current desktop environment is not proof that those ROS2 packages are installed.",
    )

    test_deps = set(xml_texts(package_xml, "test_depend"))
    add(
        rows,
        "package_xml_test_dependencies",
        "package_metadata",
        "package.xml declares basic lint/test dependencies for future ROS2 workspace CI.",
        {"ament_flake8", "ament_pep257", "python3-pytest"}.issubset(test_deps),
        f"test_deps={sorted(test_deps)}",
        "03_real_robot/ros2_qgip_stack/package.xml",
        "Lint/test declarations are not equivalent to having run colcon test.",
    )

    node_names = [
        "tf_leader_detection_node",
        "fault_injection_node",
        "pop_nis_kf_node",
        "velocity_safety_controller_node",
        "trial_supervisor_node",
    ]
    missing_entry = [name for name in node_names if f"{name} = ros2_qgip_stack.{name}:main" not in setup_text]
    missing_file = [name for name in node_names if not (PKG / f"{name}.py").exists()]
    missing_main = [name for name in node_names if "def main(" not in read_text(PKG / f"{name}.py")]
    add(
        rows,
        "setup_console_scripts",
        "entry_points",
        "setup.py exposes the five preflight nodes and every node source defines main().",
        not missing_entry and not missing_file and not missing_main,
        f"missing_entry={missing_entry}; missing_file={missing_file}; missing_main={missing_main}",
        "03_real_robot/ros2_qgip_stack/setup.py; ros2_qgip_stack/*.py",
        "Entry-point presence does not prove colcon build or runtime launch.",
    )

    add(
        rows,
        "setup_data_files",
        "entry_points",
        "setup.py installs package.xml, launch files, config files, and the resource marker.",
        all(token in setup_text for token in ("package.xml", "config/*.yaml", "launch/*.launch.py", "resource/")),
        "data_files tokens checked",
        "03_real_robot/ros2_qgip_stack/setup.py",
        "Static setup inspection does not install the package.",
    )

    add(
        rows,
        "launch_description_structure",
        "launch",
        "Launch file defines generate_launch_description(), uses OpaqueFunction, and constructs Node actions.",
        all(token in launch_text for token in ("def generate_launch_description", "OpaqueFunction", "Node(")),
        "generate_launch_description/OpaqueFunction/Node tokens checked",
        "03_real_robot/ros2_qgip_stack/launch/multi_robot_preflight.launch.py",
        "Static launch structure does not execute ros2 launch.",
    )

    ns_frame_args = ["follower_ns", "follower_frame", "leader_frames", "leader_ids", "leader_id_filter"]
    ok, missing = contains_all(launch_text, [f'DeclareLaunchArgument("{item}"' for item in ns_frame_args])
    add(
        rows,
        "launch_namespace_frame_arguments",
        "launch",
        "Launch file exposes namespace, frame, leader-list, and leader-filter arguments.",
        ok,
        f"missing={missing}",
        "03_real_robot/ros2_qgip_stack/launch/multi_robot_preflight.launch.py",
        "Argument declaration does not prove operator-selected frame calibration.",
    )

    fault_args = [
        "dropout_duration_s",
        "position_noise_std_m",
        "delay_s",
        "false_positive_rate",
        "false_negative_rate",
        "confidence_scale",
        "id_switch_probability",
    ]
    ok, missing = contains_all(launch_text, [f'DeclareLaunchArgument("{item}"' for item in fault_args])
    add(
        rows,
        "launch_fault_arguments",
        "launch",
        "Launch file exposes the software fault-injection arguments needed for preflight sweeps.",
        ok,
        f"missing={missing}",
        "03_real_robot/ros2_qgip_stack/launch/multi_robot_preflight.launch.py",
        "Software fault knobs do not replace physical occlusion or real sensor tests.",
    )

    pop_args = ["confidence_threshold", "nis_soft_threshold", "nis_hard_threshold", "r_inflation", "ghost_horizon_s", "lost_timeout_s"]
    ok, missing = contains_all(launch_text, [f'DeclareLaunchArgument("{item}"' for item in pop_args])
    add(
        rows,
        "launch_pop_nis_arguments",
        "launch",
        "Launch file exposes POP/NIS confidence, gate, inflation, ghost-horizon, and lost-timeout parameters.",
        ok,
        f"missing={missing}",
        "03_real_robot/ros2_qgip_stack/launch/multi_robot_preflight.launch.py",
        "Parameter exposure does not prove runtime calibration.",
    )

    add(
        rows,
        "launch_results_path_argument",
        "launch",
        "Launch file can pass a results CSV path to the trial supervisor.",
        'DeclareLaunchArgument("results_csv_path"' in launch_text and "results_csv_path" in node_texts,
        "results_csv_path declared and referenced",
        "multi_robot_preflight.launch.py; trial_supervisor_node.py",
        "A declared path does not prove that physical trial rows have been written.",
    )

    node_count = len(re.findall(r"\bNode\(", launch_text))
    add(
        rows,
        "launch_node_count_and_names",
        "launch",
        "Launch file instantiates exactly the five preflight nodes.",
        node_count == 5 and all(f'executable="{name}"' in launch_text for name in node_names),
        f"node_count={node_count}",
        "03_real_robot/ros2_qgip_stack/launch/multi_robot_preflight.launch.py",
        "Static Node action count does not prove nodes start successfully.",
    )

    add(
        rows,
        "selected_leader_launch_route",
        "selected_leader_route",
        "Selected-leader topic is produced by TF preflight selection and consumed by POP/NIS.",
        all(token in "\n".join([launch_text, node_texts, readme_text]) for token in ("selected_leader_topic", "leader_id", "candidate_count", "/robot_1/qgip/selected_leader")),
        "selected_leader_topic, leader_id, candidate_count, README echo command present",
        "multi_robot_preflight.launch.py; tf_leader_detection_node.py; pop_nis_kf_node.py; README.md",
        "Selected-leader route is static here; ros2 topic echo/rosbag evidence is still required.",
    )

    add(
        rows,
        "cmd_vel_shadow_boundary",
        "safety_boundary",
        "README requires shadow-mode inspection before connecting cmd_vel_safe to a real base controller.",
        "Do not connect `/robot_1/cmd_vel_safe`" in readme_text and "shadow command first" in rosbag_text,
        "README and rosbag command docs contain shadow-mode warning",
        "ros2_qgip_stack/README.md; 03_real_robot/rosbag_commands.md",
        "Documentation warning does not guarantee operator compliance.",
    )

    add(
        rows,
        "config_robot_roles",
        "configuration",
        "multi_robot_profile.yaml declares follower, leader, and distractor robot roles.",
        all(token in config_text for token in ("id: robot_1", "id: robot_2", "id: robot_3", "namespace: /robot_1")),
        "robot_1/robot_2/robot_3 tokens checked",
        "03_real_robot/ros2_qgip_stack/config/multi_robot_profile.yaml",
        "Profile roles must still match actual robot namespaces and TF frames.",
    )

    config_topics = [
        "/robot_1/detections_raw",
        "/robot_1/detections_faulty",
        "/robot_1/qgip/selected_leader",
        "/robot_1/qgip/pop_state",
        "/robot_1/qgip/mpc_debug",
        "/robot_1/qgip/trial_status",
        "/robot_1/cmd_vel_safe",
        "/robot_1/safety_state",
    ]
    add(
        rows,
        "config_topics_complete",
        "configuration",
        "multi_robot_profile.yaml lists all local detection, POP, debug, trial, command, and safety topics.",
        all(topic in config_text for topic in config_topics),
        "configured_topics=" + ";".join(topic for topic in config_topics if topic in config_text),
        "03_real_robot/ros2_qgip_stack/config/multi_robot_profile.yaml",
        "Configured topic names are not proof of runtime publishers/subscribers.",
    )

    add(
        rows,
        "config_pop_thresholds_match_manuscript",
        "configuration",
        "Profile POP/NIS gates match the manuscript thresholds tau_soft=12, tau_hard=20, gamma=10.",
        all(token in config_text for token in ("nis_soft_threshold: 12.0", "nis_hard_threshold: 20.0", "r_inflation: 10.0")),
        "soft=12.0; hard=20.0; r_inflation=10.0",
        "multi_robot_profile.yaml; RA_L_extended_working.tex",
        "Matching thresholds still need robot-environment calibration.",
    )

    add(
        rows,
        "config_controller_limits",
        "configuration",
        "Profile keeps low-speed controller limits suitable for supervised scaled-robot preflight.",
        all(token in config_text for token in ("max_speed_mps: 0.5", "control_hz: 20.0", "near_miss_distance_m: 0.25")),
        "max_speed_mps=0.5; control_hz=20; near_miss_distance_m=0.25",
        "03_real_robot/ros2_qgip_stack/config/multi_robot_profile.yaml",
        "Static values must be rechecked against platform capability and test-area safety.",
    )

    add(
        rows,
        "experiment_parameters_control_safety",
        "experiment_parameters",
        "experiment_parameters.yaml includes control frequency, horizon, timeout, headway, near-miss, and TTC abort rules.",
        all(token in experiment_text for token in ("frequency_hz: 20", "horizon_s: 1.5", "command_timeout_s: 0.2", "near_miss_distance_m: 0.25", "ttc_abort_s: 0.8")),
        "control and abort tokens checked",
        "03_real_robot/experiment_parameters.yaml",
        "Parameter file is a protocol draft, not a signed safety assessment.",
    )

    experiment_topics = ["/qgip/selected_leader", "/qgip/pop_state", "/qgip/mpc_debug", "/cmd_vel_safe", "/tf"]
    add(
        rows,
        "experiment_parameters_logging_topics",
        "experiment_parameters",
        "experiment_parameters.yaml requests logging of selected leader, POP state, MPC debug, safe command, and TF.",
        all(topic in experiment_text for topic in experiment_topics),
        "logging_topics=" + ";".join(topic for topic in experiment_topics if topic in experiment_text),
        "03_real_robot/experiment_parameters.yaml",
        "Logging plan does not prove rosbag recording was performed.",
    )

    topic_columns = ["category", "topic", "message_type", "producer", "consumer", "required_for", "log_in_bag", "minimum_rate_hz", "key_fields", "purpose"]
    add(
        rows,
        "topic_contract_schema_and_count",
        "topic_contract",
        "ros2_topic_contract.csv has the expected schema and 13 interface topics.",
        csv_has_columns(topic_contract, topic_columns) and len(topic_contract) == 13,
        f"rows={len(topic_contract)}; columns={list(topic_contract[0].keys()) if topic_contract else []}",
        "03_real_robot/ros2_topic_contract.csv",
        "Topic contract schema does not prove runtime topic rates.",
    )

    add(
        rows,
        "topic_contract_all_logged",
        "topic_contract",
        "Every topic in the contract is marked for bag logging.",
        all(row["log_in_bag"].lower() == "true" for row in topic_contract),
        "log_in_bag values=" + ";".join(sorted({row["log_in_bag"] for row in topic_contract})),
        "03_real_robot/ros2_topic_contract.csv",
        "A logging requirement is not proof of an actual rosbag.",
    )

    selected_rows = [row for row in topic_contract if row["topic"] == "/robot_1/qgip/selected_leader"]
    selected = selected_rows[0] if selected_rows else {}
    add(
        rows,
        "topic_contract_selected_leader_fields",
        "selected_leader_route",
        "Selected-leader contract includes leader_id, confidence, rank, and candidate_count fields.",
        bool(selected) and all(field in selected.get("key_fields", "") for field in ("leader_id", "confidence", "rank", "candidate_count")),
        f"key_fields={selected.get('key_fields', '')}",
        "03_real_robot/ros2_topic_contract.csv",
        "Contract fields still require runtime message inspection.",
    )

    required_metric_rows = [row for row in metric_schema if row["required"].lower() == "true"]
    add(
        rows,
        "metric_schema_required_fields",
        "metrics",
        "Metric schema has 29 rows and 28 required fields, including latency p95/p99, watchdog triggers, frame drops, clock drift, command age, and CPU/GPU telemetry.",
        len(metric_schema) == 29 and len(required_metric_rows) == 28 and all(
            field in {row["field"] for row in metric_schema}
            for field in (
                "latency_p95_ms",
                "latency_p99_ms",
                "watchdog_triggers",
                "frame_drop_count",
                "clock_drift_p95_ms",
                "cmd_vel_safe_age_p95_ms",
                "cpu_load_mean_percent",
                "gpu_load_mean_percent",
                "gpu_memory_peak_mb",
            )
        ),
        f"rows={len(metric_schema)}; required={len(required_metric_rows)}",
        "03_real_robot/real_robot_metric_schema.csv",
        "Schema completeness does not create measured metrics.",
    )

    required_metric_names = [row["field"] for row in required_metric_rows]
    missing_result_fields = [field for field in required_metric_names if field not in results_header]
    add(
        rows,
        "results_template_schema_alignment",
        "metrics",
        "real_robot_results_template.csv includes every required metric-schema field.",
        not missing_result_fields,
        f"missing_result_fields={missing_result_fields}",
        "real_robot_metric_schema.csv; real_robot_results_template.csv",
        "The template contains an example row only; it is not physical trial evidence.",
    )

    add(
        rows,
        "trial_matrices_counts",
        "trial_plan",
        "Preflight and real-robot trial matrices each define 12 planned rows.",
        len(preflight_trials) == 12 and len(real_trials) == 12,
        f"preflight_rows={len(preflight_trials)}; real_robot_rows={len(real_trials)}",
        "preflight_trials_matrix.csv; real_robot_trials_matrix.csv",
        "Planned rows are not completed runs.",
    )

    methods_text = "\n".join(row["methods"] for row in real_trials)
    add(
        rows,
        "trial_matrix_method_coverage",
        "trial_plan",
        "Real-robot trial matrix covers rule/KF/IMM/no-query/full-QGIP comparison families.",
        all(method in methods_text for method in ("rule_mpc", "std_kf_mpc", "imm_kf_mpc", "no_query_pop_mpc", "full_qgip")),
        f"methods={methods_text}",
        "03_real_robot/real_robot_trials_matrix.csv",
        "Method coverage is a plan until executed with robots.",
    )

    scenario_text = "\n".join(row["scenario"] for row in real_trials)
    add(
        rows,
        "trial_matrix_scenario_coverage",
        "trial_plan",
        "Real-robot trial matrix covers straight, braking, curve, distractor, cut-in/out, and stop-and-go scenarios.",
        all(scenario in scenario_text for scenario in ("straight_following", "lead_braking", "curved_following", "adjacent_lane_distractor", "cut_in_cut_out", "stop_and_go")),
        f"scenarios={scenario_text}",
        "03_real_robot/real_robot_trials_matrix.csv",
        "Scenario coverage is planned, not executed.",
    )

    manifest_sections = ["trial:", "hardware:", "software:", "fault_profile:", "logging:", "safety_gate:", "outcome:"]
    add(
        rows,
        "run_manifest_sections",
        "run_manifest",
        "Run manifest template contains trial, hardware, software, fault, logging, safety, and outcome sections.",
        all(section in run_manifest_text for section in manifest_sections),
        "sections=" + ";".join(section for section in manifest_sections if section in run_manifest_text),
        "03_real_robot/real_robot_run_manifest_template.yaml",
        "Blank manifest sections are not completed run metadata.",
    )

    safety_fields = ["physical_estop_checked", "cmd_vel_shadow_mode_first", "max_speed_mps", "min_headway_abort_m", "min_ttc_abort_s", "operator_line_of_sight", "test_area_clear"]
    add(
        rows,
        "run_manifest_safety_gate_fields",
        "run_manifest",
        "Run manifest safety gate requires estop, shadow mode, speed, headway/TTC abort thresholds, line-of-sight, and clear test area.",
        all(field in run_manifest_text for field in safety_fields),
        "safety_fields=" + ";".join(field for field in safety_fields if field in run_manifest_text),
        "03_real_robot/real_robot_run_manifest_template.yaml",
        "Fields must be filled and reviewed before closed-loop trials.",
    )

    logging_fields = ["rosbag_path", "per_frame_csv_path", "metric_summary_csv_path", "incident_report_path", "video_path", "clock_sync_method"]
    add(
        rows,
        "run_manifest_logging_fields",
        "run_manifest",
        "Run manifest logging section requires rosbag, per-frame CSV, metric summary, incident report, video, and clock sync fields.",
        all(field in run_manifest_text for field in logging_fields),
        "logging_fields=" + ";".join(field for field in logging_fields if field in run_manifest_text),
        "03_real_robot/real_robot_run_manifest_template.yaml",
        "Logging placeholders are not evidence that data were recorded.",
    )

    json_needles = ["loads_payload", "dumps_payload", "normalize_detection", "normalize_detections", "select_front_leader", "confidence", "stamp_s"]
    add(
        rows,
        "json_contract_helpers",
        "json_contract",
        "JSON helper module normalizes detections and selects a front leader with confidence and stamp fields.",
        all(token in read_text(PKG / "json_contract.py") for token in json_needles),
        "json helper function tokens checked",
        "03_real_robot/ros2_qgip_stack/ros2_qgip_stack/json_contract.py",
        "Schema helpers do not freeze custom ROS2 message definitions.",
    )

    add(
        rows,
        "pop_state_json_fields",
        "json_contract",
        "POP/NIS node publishes mode, kinematic state, covariance, NIS, ghost age, and leader id.",
        all(token in read_text(PKG / "pop_nis_kf_node.py") for token in ("mode", "x", "y", "vx", "vy", "covariance_diag", "nis", "ghost_age_s", "leader_id")),
        "POP state field tokens checked",
        "03_real_robot/ros2_qgip_stack/ros2_qgip_stack/pop_nis_kf_node.py",
        "Field presence does not prove real-time message publication.",
    )

    add(
        rows,
        "controller_debug_json_fields",
        "json_contract",
        "Velocity safety controller publishes selected speed, headway, TTC, safety stop, and diagnostic reason.",
        all(token in read_text(PKG / "velocity_safety_controller_node.py") for token in ("selected_speed_mps", "headway_m", "ttc_s", "safety_stop", "reason")),
        "controller debug field tokens checked",
        "03_real_robot/ros2_qgip_stack/ros2_qgip_stack/velocity_safety_controller_node.py",
        "Debug field presence does not prove controller timing or actuator safety.",
    )

    add(
        rows,
        "trial_supervisor_status_fields",
        "json_contract",
        "Trial supervisor publishes min-distance, min-TTC, lost/near-miss flags, and latency fields.",
        all(token in read_text(PKG / "trial_supervisor_node.py") for token in ("min_distance_m", "min_ttc_s", "lost", "near_miss", "latency_mean_ms", "latency_p95_ms")),
        "trial supervisor status tokens checked",
        "03_real_robot/ros2_qgip_stack/ros2_qgip_stack/trial_supervisor_node.py",
        "Online status fields are not physical trial summaries until logged in runs.",
    )

    rosbag_topics = ["/robot_1/odom", "/robot_2/odom", "/robot_3/odom", "/robot_1/detections_raw", "/robot_1/detections_faulty", "/robot_1/qgip/pop_state", "/robot_1/qgip/mpc_debug", "/robot_1/qgip/trial_status", "/robot_1/cmd_vel_safe"]
    add(
        rows,
        "rosbag_preflight_topics",
        "logging",
        "rosbag_commands.md includes follower/leader/distractor odometry, detections, POP, debug, trial, and safe-command topics.",
        all(topic in rosbag_text for topic in rosbag_topics),
        "preflight topics present=" + ";".join(topic for topic in rosbag_topics if topic in rosbag_text),
        "03_real_robot/rosbag_commands.md",
        "Recording commands are instructions, not recorded bags.",
    )

    add(
        rows,
        "documentation_build_and_dry_run",
        "operator_documentation",
        "README documents colcon build, sourcing, dry launch, topic echo inspection, and no full-scale deployment boundary.",
        all(token in readme_text for token in ("colcon build", "source install/setup.bash", "ros2 launch", "ros2 topic echo", "not a full-scale ACC vehicle deployment")),
        "README build/dry-run/boundary tokens checked",
        "03_real_robot/ros2_qgip_stack/README.md",
        "Operator documentation is not an executed build log.",
    )

    add(
        rows,
        "incident_report_template",
        "safety_documentation",
        "Incident report template exists for contact, near-miss, abort, and safety-stop documentation.",
        exists := (REAL / "incident_report_template.md").exists() and all(token in read_text(REAL / "incident_report_template.md").lower() for token in ("contact", "near", "abort", "safety")),
        f"incident_report_template_ok={exists}",
        "03_real_robot/incident_report_template.md",
        "Template presence does not imply any incident occurred or was reviewed.",
    )

    nonclaim_terms = [
        "does not prove ROS2 launch/build success",
        "does not prove physical robot validation",
        "not replace full-scale vehicle testing",
    ]
    report_sources = "\n".join(
        read_text(path)
        for path in (
            PACKAGE / "ros2_static_interface_audit_report_20260604.md",
            PACKAGE / "real_robot_preflight_readiness_report_20260603.md",
            PACKAGE / "pre_real_robot_validation_protocol_20260603.md",
            STACK / "README.md",
            ROOT / "01_manuscript" / "RA_L_extended_working.tex",
        )
        if path.exists()
    )
    add(
        rows,
        "preflight_nonclaim_boundary",
        "audit_boundary",
        "Existing reports, README, and manuscript state the boundary below ROS2 build, physical validation, and full-scale/full-size vehicle validation.",
        all(term in report_sources for term in nonclaim_terms),
        "boundary reports scanned",
        "06_submission_package/*real_robot*; ros2_static_interface_audit_report_20260604.md; ros2_qgip_stack/README.md; RA_L_extended_working.tex",
        "This validator itself remains below ROS2 build/launch and below physical validation.",
    )

    add(
        rows,
        "offline_validator_nonclaim",
        "audit_boundary",
        "This validator is explicitly offline and does not require ROS2, colcon, rosbag, or robot hardware.",
        True,
        "offline static validator; no ROS2 imports or robot I/O",
        "05_analysis_scripts/generate_real_robot_preflight_validation.py",
        "Passing this validator means the preflight package is internally consistent, not that a robot run succeeded.",
    )

    failed = [row for row in rows if row.status != "PASS"]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ValidationRow.__annotations__.keys()))
        writer.writeheader()
        writer.writerows([row.__dict__ for row in rows])

    report_lines = [
        "# Real-Robot Preflight Offline Validation Report, 2026-06-04",
        "",
        "## Decision",
        "",
        f"The offline real-robot preflight validator checks {len(rows)} package-structure, launch, configuration, topic-contract, JSON-contract, metric-template, run-manifest, logging, documentation, and boundary gates without requiring a ROS2 installation.",
        f"Passed: {len(rows) - len(failed)}",
        f"Failed: {len(failed)}",
        "All offline real-robot preflight validation checks passed." if not failed else "One or more offline preflight validation checks failed.",
        "",
        "## Coverage",
        "",
        "- ROS2 package metadata, console scripts, launch file, config profile, and Python syntax.",
        "- Selected-leader route from TF preflight selection to POP/NIS filtering and logging.",
        "- Fault-injection, POP/NIS, speed-limit, trial-status, and safe-command controls.",
        "- Topic contract, rosbag plan, metric schema, results template, trial matrices, run manifest, and incident-report template.",
        "",
        "## Boundary",
        "",
        "This offline validator does not prove ROS2 build success, does not prove ros2 launch success, does not produce a rosbag, does not measure timing, does not command robot hardware, and does not contain completed physical robot trial data. It is the last static package consistency layer before moving to a ROS2 workspace and a supervised robot test area.",
    ]
    if failed:
        report_lines.extend(["", "## Failed Checks", ""])
        for row in failed:
            report_lines.append(f"- `{row.check_id}`: {row.evidence}")

    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8", newline="\n")
    print(OUT_CSV)
    print(OUT_REPORT)
    print(f"passed={len(rows) - len(failed)} failed={len(failed)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
