# Real-Robot Incident Report Template

Use one report for every contact, near miss, safety stop, operator stop, watchdog timeout,
ODD exit, topic loss, or trial exclusion.

## Trial Metadata

- Trial ID:
- Date and local time:
- Operator:
- Observer:
- Scenario:
- Method:
- Fault profile:
- Rosbag path:
- Run manifest path:

## Incident Classification

- [ ] Contact
- [ ] Near miss
- [ ] Safety stop
- [ ] Operator E-stop
- [ ] Autonomous abort
- [ ] Watchdog timeout
- [ ] Robot left ODD boundary
- [ ] Topic/timestamp failure
- [ ] Trial exclusion
- [ ] Other:

## Timeline

| Time | Event |
| --- | --- |
|  |  |

## Quantitative Snapshot

- Minimum headway:
- Minimum TTC:
- POP mode before incident:
- NIS before incident:
- Commanded speed before incident:
- Safety-supervisor state:
- Abort reason:
- Last valid detection timestamp:

Machine-readable fields for audit extraction:

- autonomous abort:
- abort reason:

## Root-Cause Notes

Describe the most likely immediate cause. Do not assign the incident to QGIP, POP/NIS,
MPC, hardware, or operator action unless the rosbag and CSV evidence support it.

## Data Integrity

- [ ] Rosbag exists and is readable.
- [ ] Run manifest exists.
- [ ] Per-frame CSV extracted.
- [ ] Metric summary row updated.
- [ ] Video or operator observation linked if available.

## Manuscript Handling

- [ ] Include in denominator.
- [ ] Count as safety stop.
- [ ] Count as near miss.
- [ ] Count as contact.
- [ ] Exclude only for documented logging or hardware invalidation.

Exclusion reason, if applicable:
