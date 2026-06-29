# FAIR metadata and source-data dictionary

Date: 2026-06-03

Dataset title: Source data for "Resilient Vehicle Following under Perception
Uncertainty: A Neuro-Symbolic Approach with Predictive Object Permanence" (extended
simulation-first package).

## Summary

This directory contains processed source-data tables supporting the simulation-first
manuscript. The files trace the main CARLA benchmark, nominal N=1000 sanity check,
stress-suite summaries, paired statistics, NIS diagnostics, dataset split audit,
extended claim-to-evidence matrix, manuscript/claim/figure QA audits, and ROS2
preflight traceability. The files are designed as figure/table/audit source data,
not as a complete raw CARLA log archive.

## Access status

- Current package status: included in the structured manuscript package.
- Recommended submission status: deposit the complete package in a DOI-backed general
  repository before Nature-family submission, or provide a private reviewer link during
  review.
- Licence: to be confirmed by the author/institution before public release.
- Restrictions: CARLA simulator assets, scenario assets, and third-party platform files
  may have their own licences; do not redistribute assets not owned by the authors.

## File inventory

| File | Contents | Supports |
|---|---|---|
| `main_benchmark_source.csv` | Main N=300 benchmark table rows | Main comparison table |
| `main1000_nominal_source.csv` | N=1000 nominal sanity-check rows | Nominal non-discrimination boundary |
| `carla_scenario_coverage_source.csv` | Scenario-class to evidence mapping | Scenario coverage table |
| `stress_summary_combined.csv` | Stress-suite summary rows | Ambiguity, detector/timing, raw-like, boundary tables |
| `pairwise_stats_combined.csv` | Paired McNemar/bootstrap comparison statistics | Primary ambiguity claims and CIs |
| `figure_stress_leader_metrics.csv` | LeaderAcc/ID-switch plotting source | Target-consistency stress figures |
| `extended_stress_qgip_summary.csv` | QGIP-only extended stress summary | Extended stress synthesis figure/table |
| `claim_evidence_matrix.csv` | Claim, evidence, boundary, source, verifier mapping | Claim-to-evidence matrix |
| `fig_nature_system_evidence_source.csv` | Source data for the Nature-style system/evidence composite | Figure 1 panels b and c |
| `final_dataset_split_check.csv` | Split counts, existing/missing files, town composition | Dataset split audit |
| `final_dataset_split_overlap.csv` | Pairwise split-overlap counts | Dataset leakage audit |
| `final_dataset_split_check.md` | Human-readable split audit | Dataset leakage audit |
| `carla_nis_diagnostic_summary.csv` | Initial CARLA NIS logging-chain diagnostic summary | NIS logging sanity check |
| `carla_nis_diagnostic_episode_results.csv` | Per-episode initial NIS diagnostic rows | NIS logging sanity check |
| `carla_nis_noise_sweep_qgip100_summary.csv` | QGIP detector-noise/NIS sweep summary | NIS noise table |
| `carla_nis_noise_sweep_figure_data.csv` | Compact NIS noise figure source | NIS noise panel |
| `carla_nis_outlier_qgip100_summary.csv` | QGIP NIS outlier/ambiguity summary | NIS outlier table |
| `carla_nis_outlier_figure_data.csv` | Compact outlier figure source | NIS outlier panel |
| `synthetic_pop_nis300_summary.csv` | Local POP/NIS mechanism-check summary | Estimator sanity check only |
| `synthetic_pop_nis300_episode_results.csv` | Per-episode local POP/NIS mechanism-check rows | Estimator sanity check only |
| `figure_accessibility_metrics.csv` | Grayscale/deuteranopia-oriented figure QA metrics | Figure accessibility QA |
| `simulation_protocol_registry.csv` | Experiment/diagnostic/audit/preflight protocol-to-artifact mapping | Methods provenance and protocol traceability |
| `real_robot_preflight_validation.csv` | Offline package-structure, launch, config, topic, JSON, metric, manifest, and logging checks | Real-robot preflight static validation |
| `real_robot_offline_dryrun_trace.csv` | Deterministic ROS2-less selected-leader/fault-injection/POP-NIS dry-run frame trace | Pre-ROS2 behavior smoke test |
| `real_robot_offline_dryrun_summary.csv` | PASS/FAIL summary for offline dry-run behavior gates | Pre-ROS2 behavior smoke test |
| `real_robot_software_smoke_test.csv` | Executable pure-Python checks for POP/NIS parity, fault injection, JSON contracts, and controller-proxy invariants | Pre-ROS2 software smoke test |
| `ros2_workspace_ci_audit.csv` | Local pure-core pytest and ROS2 workspace CI/build-test readiness checks | Pre-HIL ROS2 workspace CI readiness |
| `ros2_runtime_telemetry_audit.csv` | Runtime timing, frame-drop, watchdog, clock-drift, command-age, and CPU/GPU telemetry readiness checks | Pre-HIL and pre-robot timing instrumentation readiness |
| `ros2_runtime_telemetry_dryrun_trace.csv` | Synthetic schema-compatible runtime telemetry trace for parser QA | Telemetry parser dry-run only |
| `ros2_runtime_telemetry_dryrun_summary.csv` | PASS/FAIL latency, frame-drop, watchdog, command-age, clock-drift, and CPU/GPU summary checks from the synthetic telemetry trace | Telemetry summary-chain dry-run only |
| `ros2_hil_replay_manifest_audit.csv` | Machine-readable checks for HIL replay manifest, rosbag topic coverage, ROS clock playback, safety-state logging, and disabled actuator bridge | Pre-HIL replay readiness audit |
| `fig13_offline_dryrun_contract_timeline_v2_source_data.csv` | Source data for the offline dry-run contract-timeline diagnostic figure | Pre-ROS2 behavior smoke-test figure |
| `pre_real_robot_gate_audit.csv` | Go/no-go gate audit before ROS2/HIL/physical claims | Pre-real-robot readiness synthesis |
| `real_robot_template_summary.csv` | Summary produced from the empty/example real-robot results template | Physical-validation template check only |
| `statistical_claim_audit.csv` | Numerical manuscript-claim checks against staged source data | Statistical claim drift control |
| `manuscript_argument_traceability.csv` | Reader-question and boundary checks for the extended manuscript | Manuscript narrative traceability |
| `safety_case_claim_graph.csv` | Bounded safety-case claim graph linking top-level claims to evidence, boundaries, and next required validation | Safety-claim discipline only |
| `fig_safety_case_evidence_map_source.csv` | Source rows for the safety-case evidence-boundary figure | Safety-case figure source data |
| `fig_evidence_coverage_matrix_source.csv` | Source rows for the protocol-to-claim evidence coverage matrix | Evidence coverage figure source data |
| `fig_simulation_effect_size_source.csv` | Source rows for the simulation effect-size and finite-sample boundary figure | Effect-size synthesis figure source data |
| `fig_simulation_stress_atlas_source.csv` | Source rows for the simulation stress atlas linking evidence scale, stress outcomes, ambiguity effects, and NIS response | Simulation stress-atlas figure source data |
| `fig12_validation_boundary_narrative_v4_source_data.csv` | Source rows for the pre-real-robot validation-boundary narrative figure | Pre-real-robot validation-boundary figure source data |
| `ros2_static_interface_audit.csv` | Static checks for ROS2 topics, launch/config wiring, templates, and safety boundary | Pre-real-robot interface readiness |
| `publication_figure_qa.csv` | Publication-figure export, source-data, vector, raster, and embedding QA rows | Figure production QA |
| `source_data_provenance_audit.csv` | Source inventory, figure-to-source-data mapping, table-to-source-data mapping, FAIR/deposit/reproducibility checks | Source-data provenance audit |

## Common variable dictionary

| Variable family | Definition | Unit / allowed values |
|---|---|---|
| `condition_id` | Reproducible stress or diagnostic condition identifier | string |
| `method` | Method or ablation identifier | string |
| `layer` | Stress layer, such as ambiguity, detector/timing, raw-like, or diagnostic | string |
| `scenario` | Scenario or perturbation label | string |
| `n` | Number of episodes summarized | episodes |
| `success_count`, `success_rate` | Episodes completing the route/task and corresponding rate | count, fraction [0,1] |
| `lost_count`, `lost_rate` | Episodes ending in fail-safe target-loss stop and corresponding rate | count, fraction [0,1] |
| `collision_count`, `collision_rate` | Observed collision/contact count and rate | count, fraction [0,1] |
| `near_miss_count`, `near_miss_rate` | Near-miss count and rate under the configured threshold | count, fraction [0,1] |
| `*_ci95_low`, `*_ci95_high` | 95% confidence interval bounds for rate metrics | fraction [0,1] |
| `zero_collision_rule3_upper` | Rule-of-three upper bound for zero observed collisions | fraction |
| `leaderacc_mean` | Mean fraction of frames assigned to the intended leader | fraction [0,1] |
| `wrongleaderframes_mean` | Mean wrong-leader frame count per episode | frames/episode |
| `idswitches_mean` | Mean target identity switches per episode | switches/episode |
| `recoverytime_mean` | Mean recovery time after a perturbation/dropout | seconds if logged by runner |
| `jerk_mean`, `jerk_p95` | Mean and 95th-percentile control jerk summaries | m/s^3 |
| `mindistance_mean`, `minheadway_mean` | Minimum-distance/headway summary statistics | metres |
| `minttc_mean` | Minimum time-to-collision summary | seconds |
| `nismean_mean` | Episode-averaged mean Normalized Innovation Squared | dimensionless |
| `nisp95_mean` | Mean episode-level NIS 95th percentile | dimensionless |
| `nissoftviolations_mean` | Mean soft-gate violation count | events/episode |
| `nishardviolations_mean` | Mean hard-gate violation count | events/episode |
| `kfsoftupdates_mean`, `kfhardresets_mean` | Mean Kalman soft updates and hard resets | events/episode |
| `paired_n` | Number of paired episodes used in comparison | episode pairs |
| `*_diff_ref_minus_cmp` | Paired difference, reference minus comparator | metric-specific |
| `latency_mean_ms`, `latency_p95_ms`, `latency_p99_ms` | End-to-end runtime latency summaries planned for ROS2/HIL/robot validation | ms |
| `frame_drop_count` | Missing or late message-frame count from runtime telemetry | count |
| `clock_drift_p95_ms` | 95th percentile ROS-vs-wall clock drift | ms |
| `cmd_vel_safe_age_p95_ms` | 95th percentile age of the latest safe shadow command | ms |
| `cpu_load_mean_percent`, `gpu_load_mean_percent` | Mean robot-computer CPU/GPU utilization during a run | percent |
| `gpu_memory_peak_mb` | Peak GPU memory allocation during a run | MB |

## Provenance

Processed source data were generated from CARLA episode summaries and analysis scripts in
`05_analysis_scripts/`. The Nature-style system/evidence composite is generated by
`generate_nature_main_figure.py`; the extended figures are generated by
`generate_extended_artifacts.py`; short-package tables and earlier source tables are
generated by `generate_paper_sim_artifacts.py` and NIS diagnostic scripts.

The current protocol and audit layer is generated by `generate_simulation_protocol_registry.py`,
`generate_real_robot_preflight_validation.py`,
`generate_real_robot_software_smoke_test.py`,
`generate_ros2_workspace_ci_audit.py`,
`generate_ros2_runtime_telemetry_audit.py`,
`generate_ros2_runtime_telemetry_dryrun.py`,
`generate_ros2_hil_replay_manifest_audit.py`,
`generate_real_robot_offline_dryrun.py`,
`fig13_offline_dryrun_contract_timeline_v2.py`,
`generate_pre_real_robot_gate_audit.py`,
`generate_statistical_claim_audit.py`,
`generate_manuscript_argument_audit.py`, `generate_safety_case_audit.py`,
`generate_safety_case_figure.py`,
`generate_evidence_coverage_matrix.py`,
`generate_simulation_effect_size_figure.py`,
`generate_simulation_stress_atlas_figure.py`,
`fig12_validation_boundary_narrative_v4.py`,
`generate_ros2_static_interface_audit.py`,
`generate_publication_figure_qa.py`, `generate_figure_accessibility_qa.py`, and
`generate_source_data_provenance_audit.py`. These scripts create reviewer-facing
drift-control artifacts; they do not create new raw CARLA evidence, a DOI-backed
repository record, or completed physical robot trial data.

Synthetic POP/NIS files are local mechanism checks. They should not be described as CARLA
or real-robot validation evidence.

## FAIR checklist

| Principle | Current status | Submission action |
|---|---|---|
| Findable | Files are named and packaged locally. | Deposit a release in a DOI-backed repository and add the DOI to the manuscript. |
| Accessible | Files are in the structured package. | Provide public repository access or private reviewer access before submission. |
| Interoperable | CSV and Markdown formats are used. | Preserve CSV, add README/data dictionary, and include script-to-file mapping. |
| Reusable | Provenance and variable definitions are documented here. | Add licence, repository metadata, software environment, and version tag. |

## Missing information before public deposit

- Repository name and DOI/accession.
- Data/code licence approved by the author or institution.
- Preferred citation text for the deposited dataset.
- Whether raw CARLA logs or only processed source data will be deposited.
- Any simulator asset or third-party licence restrictions affecting redistribution.
