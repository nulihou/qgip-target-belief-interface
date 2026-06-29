# Suspended-Wheel Preflight Evidence Record

Date: 2026-06-12  
Evidence class: suspended-wheel preflight / command-chain diagnostic  
Platform: two ROS2 wheeled robots, Jetson ROS 2 Humble  
Local source folder: `run_artifacts/`

## Result Summary

The suspended-wheel preflight completed three diagnostic runs:

| Trial folder | Perturbation | Observed result | Valid use |
| --- | --- | --- | --- |
| `nominal_003` | none | selected leader was `robot_2`; two-robot controller chain ran normally | nominal leader-selection and command-chain sanity check |
| `dropout05_001` | 0.5 s software dropout | TRACKING with GHOST/DEGRADED behavior; `robot_2` remained selected | short-dropout POP/NIS recovery evidence |
| `dropout18_001` | 1.8 s software dropout | TRACKING -> GHOST -> LOST -> TRACKING; zero-speed commands during unreliable-target intervals | long-dropout LOST and conservative-command evidence |

Safety bridge constraints:

- maximum bridge speed: 0.05 m/s;
- watchdog: 0.20 s;
- final follower state: four wheels directly confirmed at 0 rps;
- no residual QGIP, rosbag, tegrastats, or leader-driver processes were reported.

## Interpretation

This evidence supports a limited readiness claim:

> The Jetson Nano ROS2 two-robot stack exercised the target-belief command chain, produced expected POP/NIS mode transitions under short and long software dropout, and generated conservative safe-command behavior before on-ground trials.

This evidence must **not** be counted as an on-ground physical validation result.

## Excluded Metrics

The following fields are invalid for physical-performance reporting because suspended-wheel odometry virtually integrates while the chassis remains stationary:

- route completion / physical success;
- near-miss;
- minimum distance;
- TTC;
- headway tracking accuracy;
- physical safety-stop rate;
- contact-rate denominator.

## Missing Machine-Readable Artifacts

The local folder received by the paper side contains:

- `manifest.yaml`;
- `operator_notes.md`;
- `incident_report.md`.

The following manifest-referenced artifacts were not present in the local transfer:

- `bag/`;
- `bag_info.txt`;
- `trial_status.csv`;
- `tegrastats.log`;
- topic-rate logs;
- video.

If these files still exist on the robot under `~/qgip_runs/20260612_suspended_preflight/`, copy them back before making a full audit claim.

## Paper-Safe Wording

Recommended:

> A suspended-wheel preflight confirmed the ROS2 target-belief command chain before on-ground trials. The nominal run selected `robot_2`, 0.5 s dropout produced TRACKING/GHOST/DEGRADED behavior, and 1.8 s dropout produced TRACKING -> GHOST -> LOST -> TRACKING with zero-speed safe commands during unreliable-target intervals. Because the chassis was suspended, odometry-derived distance, TTC, near-miss, and route-completion fields are excluded from physical-performance reporting.

Avoid:

- "The physical robot experiment is complete."
- "The suspended-wheel run proves collision safety."
- "The suspended-wheel run proves real-world following performance."

## Next Required Step

Proceed to on-ground low-speed trials only after:

1. physical E-stop is checked and recorded as `physical_estop_checked: true`;
2. rosbag and telemetry capture are confirmed;
3. nominal suspended-wheel and dropout preflights are archived;
4. operator line-of-sight and stop authority are assigned.

