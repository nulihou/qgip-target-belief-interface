# Paper-Ready Simulation Tables

## Main Benchmark

| Method | N | Success | Collision | Lost | Mean jerk |
| --- | ---: | ---: | ---: | ---: | ---: |
| E2E Baseline (No MPC) | 300 | 8.3\% | 86.3\% | 5.3\% | -- |
| Rule-Based + MPC | 300 | 69.0\% | 0.0\% | 31.0\% | -- |
| Modular PID | 300 | 33.0\% | 58.7\% | 8.3\% | 43.250 |
| Std KF + MPC | 300 | 73.3\% | 0.0\% | 26.7\% | 0.103 |
| QGIP-Net (Ours) | 300 | 76.7\% | 0.0\% | 23.3\% | 0.112 |

## Nominal Main-Default N=1000 Sanity Check

| Method | N | Success | Collision | Lost | Near-miss | Mean min distance | NIS mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QGIP-Net (Ours) | 1000 | 735 (73.5\%) | 0 (0.0\%) | 265 (26.5\%) | 0 (0.0\%) | 14.98 m | 0.359 |
| Std KF + MPC | 1000 | 735 (73.5\%) | 0 (0.0\%) | 265 (26.5\%) | 0 (0.0\%) | 14.98 m | -- |
| Rule + MPC | 1000 | 735 (73.5\%) | 0 (0.0\%) | 265 (26.5\%) | 0 (0.0\%) | 14.98 m | -- |

## Scenario-Class Coverage

| Scenario | Conditions | Layer | N/method | Success | Collision | Lost | Evidence role |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| straight/curve following | `main_default` | planner_input | 1000 | 73.5\% | 0.0\% | 26.5\% | LeaderAcc 100.0% (scale sanity) |
| curve following | `raw_glare` | raw_sensor_like | 100 | 76.0\% | 0.0\% | 24.0\% | LeaderAcc 100.0% (detector-level glare approximation) |
| following with dropout | `raw_lidar_dropout` | raw_sensor_like | 100 | 76.0\% | 0.0\% | 24.0\% | LeaderAcc 100.0% (detector-level LiDAR-dropout approximation) |
| lead braking | `fn_50; delay_200` | detector/timing | 300 | 72.7\% | 0.0\% | 27.3\% | LeaderAcc 100.0%; delay matched (false negatives and 200 ms delay) |
| adjacent-lane distractor | `fp_10` | ambiguity | 300 | 73.0\% | 0.0\% | 27.0\% | QGIP LeaderAcc 86.2% vs no-query 53.2% (false-positive ambiguity) |
| cut-in/cut-out identity | `idswitch` | ambiguity | 300 | 73.0\% | 0.0\% | 27.0\% | QGIP LeaderAcc 90.7% vs Std KF 56.0% (ID-switch ambiguity) |
| combined boundary ambiguity | `fp20_idswitch20` | boundary | 100 | 77.0\% | 0.0\% | 23.0\% | QGIP LeaderAcc 80.0% vs no-query 47.8% (stronger false positives plus ID switches) |

## Primary Ambiguity Stress

| Condition | Method | N | Success | Collision | Lost | LeaderAcc | WrongFrames | IDSwitches |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `fp_10` | Rule + MPC | 300 | 73.0\% | 0.0\% | 27.0\% | 43.8\% | 269.7 | 57.0 |
| `fp_10` | QGIP no-query/no-gating | 300 | 73.0\% | 0.0\% | 27.0\% | 53.2\% | 221.3 | 151.1 |
| `fp_10` | QGIP-Net | 300 | 73.0\% | 0.0\% | 27.0\% | 86.2\% | 66.6 | 62.5 |
| `idswitch` | Rule + MPC | 300 | 73.0\% | 0.0\% | 27.0\% | 47.7\% | 252.0 | 155.2 |
| `idswitch` | Std KF + MPC | 300 | 73.0\% | 0.0\% | 27.0\% | 56.0\% | 208.0 | 180.6 |
| `idswitch` | QGIP-Net | 300 | 73.0\% | 0.0\% | 27.0\% | 90.7\% | 46.2 | 39.2 |

## Detector/Timing Stress

| Condition | Method | N | Success | Collision | Lost | LeaderAcc | WrongFrames | IDSwitches |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `fn_50` | std_kf | 300 | 72.7\% | 0.0\% | 27.3\% | 100.0\% | 0.0 | 0.0 |
| `fn_50` | imm_kf | 300 | 72.7\% | 0.0\% | 27.3\% | 100.0\% | 0.0 | 0.0 |
| `fn_50` | qgip | 300 | 72.7\% | 0.0\% | 27.3\% | 100.0\% | 0.0 | 0.0 |
| `delay_200` | std_kf | 300 | 72.7\% | 0.0\% | 27.3\% | 100.0\% | 0.0 | 0.0 |
| `delay_200` | imm_kf | 300 | 72.7\% | 0.0\% | 27.3\% | 100.0\% | 0.0 | 0.0 |
| `delay_200` | qgip | 300 | 72.7\% | 0.0\% | 27.3\% | 100.0\% | 0.0 | 0.0 |

## Raw-Sensor-Like Stress

| Condition | Method | N | Success | Collision | Lost | LeaderAcc | WrongFrames | IDSwitches |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `raw_glare` | Detector/Tracker + MPC | 100 | 76.0\% | 0.0\% | 24.0\% | 100.0\% | 0.0 | 0.0 |
| `raw_glare` | QGIP-Net | 100 | 76.0\% | 0.0\% | 24.0\% | 100.0\% | 0.0 | 0.0 |
| `raw_lidar_dropout` | Detector/Tracker + MPC | 100 | 76.0\% | 0.0\% | 24.0\% | 100.0\% | 0.0 | 0.0 |
| `raw_lidar_dropout` | QGIP-Net | 100 | 76.0\% | 0.0\% | 24.0\% | 100.0\% | 0.0 | 0.0 |

## Supplemental Boundary Stress

| Condition | Method | N | Success | Collision | Lost | LeaderAcc | WrongFrames | IDSwitches |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `fp_20` | Rule + MPC | 100 | 77.0\% | 0.0\% | 23.0\% | 36.8\% | 303.4 | 105.4 |
| `fp_20` | QGIP no-query/no-gating | 100 | 77.0\% | 0.0\% | 23.0\% | 48.4\% | 242.8 | 189.7 |
| `fp_20` | QGIP-Net | 100 | 77.0\% | 0.0\% | 23.0\% | 80.4\% | 94.1 | 111.7 |
| `idswitch_40` | Rule + MPC | 100 | 77.0\% | 0.0\% | 23.0\% | 43.9\% | 270.6 | 225.8 |
| `idswitch_40` | Std KF + MPC | 100 | 77.0\% | 0.0\% | 23.0\% | 54.4\% | 212.9 | 228.3 |
| `idswitch_40` | QGIP-Net | 100 | 77.0\% | 0.0\% | 23.0\% | 91.0\% | 44.8 | 46.3 |
| `fp20_idswitch20` | Rule + MPC | 100 | 77.0\% | 0.0\% | 23.0\% | 36.2\% | 306.7 | 237.4 |
| `fp20_idswitch20` | QGIP no-query/no-gating | 100 | 77.0\% | 0.0\% | 23.0\% | 47.8\% | 245.4 | 260.1 |
| `fp20_idswitch20` | QGIP-Net | 100 | 77.0\% | 0.0\% | 23.0\% | 80.0\% | 96.4 | 126.5 |
