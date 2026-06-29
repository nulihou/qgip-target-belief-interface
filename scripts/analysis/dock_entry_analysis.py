#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dock-Entry 结构性分析（Step 3.2 证据链）

目标：
- 从日志中提取“首次进入 Dock/G3”的相对几何位置与姿态误差（x_rel/y_rel/psi_rel_deg）
- 输出条件概率表：P(lane_misalignment | entered_from_front/rear)
- 输出 x_rel 直方图（按 success/fail 分色，可选）

依赖（两种口径都支持）：
- **优先**使用 trajectory 中直接记录的：`x_rel/y_rel/psi_rel_deg`（目标车坐标系）
- 若旧日志缺失上述字段，则使用：
  - `target_position`（episode级字段）
  - `ref_yaw_deg`（Dock诊断里记录的 lane yaw / 参考yaw）
  反算出 x_rel/y_rel/psi_rel_deg

坐标系：
- x 轴指向目标车后方（与目标车朝向相反），因此：x_rel > 0 表示 ego 在目标车后方；x_rel < 0 表示在前方

备注：
- lane_misalignment 这里按“navsucc8=True 且 navsucc4=False”（统一口径，min-dist）近似
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.analysis.unified_episode_evaluator import evaluate_episode  # type: ignore


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    eps: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                eps.append(json.loads(line))
            except Exception as e:
                raise RuntimeError(f"Failed to parse JSONL at {path}:{line_no}: {e}") from e
    return eps


def _first_dock_entry_step(traj: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    返回 trajectory 中首次进入 Dock 的那一帧（dock_mode==True 或 phase==G3）。
    """
    for t in traj:
        if not isinstance(t, dict):
            continue
        # 入口判定尽量宽松：
        # - dock_mode==True（最直接）
        # - phase==G3（有些日志阶段标记会提前切到G3）
        # - 或者出现 Dock诊断（ref_yaw/e_y/e_psi/dock_submode）
        if bool(t.get("dock_mode")) or str(t.get("phase", "")) == "G3":
            return t
        if t.get("ref_yaw_deg") is not None:
            return t
        if t.get("e_y") is not None or t.get("e_psi_deg") is not None:
            return t
    return None


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _wrap_deg(a: float) -> float:
    while a > 180:
        a -= 360
    while a < -180:
        a += 360
    return a


def _compute_rel_from_pos_yaw(
    ego_x: float,
    ego_y: float,
    ego_yaw_deg: float,
    tgt_x: float,
    tgt_y: float,
    ref_yaw_deg: float,
) -> Tuple[float, float, float]:
    """
    用 episode.target_position + entry.ref_yaw_deg 计算 (x_rel, y_rel, psi_rel_deg)。

    ref_yaw_deg：lane-consistent 参考yaw（优先）
    """
    import math

    yaw = math.radians(float(ref_yaw_deg))
    fx, fy = math.cos(yaw), math.sin(yaw)
    bx, by = -fx, -fy  # x轴指向“车后”
    rx, ry = math.cos(yaw - math.pi / 2.0), math.sin(yaw - math.pi / 2.0)  # 右侧方向

    dx = float(ego_x) - float(tgt_x)
    dy = float(ego_y) - float(tgt_y)

    x_rel = dx * bx + dy * by
    y_rel = dx * rx + dy * ry
    psi_rel = _wrap_deg(float(ego_yaw_deg) - float(ref_yaw_deg))
    return float(x_rel), float(y_rel), float(psi_rel)


def _bin_xrel(x: float) -> str:
    # 简单分箱，便于肉眼看分布
    if x < -5:
        return "< -5"
    if x < -2:
        return "[-5,-2)"
    if x < 0:
        return "[-2,0)"
    if x < 1:
        return "[0,1)"
    if x < 2:
        return "[1,2)"
    if x < 5:
        return "[2,5)"
    return ">= 5"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-jsonl", type=str, required=True)
    ap.add_argument("--output-md", type=str, default="results/proto_main_eval/dock_entry_analysis.md")
    ap.add_argument("--output-png", type=str, default="results/proto_main_eval/dock_entry_analysis_xrel_hist.png")
    ap.add_argument("--x-front-thresh", type=float, default=0.5, help="entered_from_front if x_rel < -x_front_thresh (note: x_rel<0 means in front)")
    args = ap.parse_args()

    in_path = Path(args.input_jsonl)
    eps = _load_jsonl(in_path)

    rows: List[Dict[str, Any]] = []
    missing = 0

    for ep in eps:
        if ep.get("valid") is False:
            continue

        ev = evaluate_episode(ep)
        traj = ep.get("trajectory", []) or []
        # 兼容：有些日志把轨迹塞在 phase_results.G2/G3 下
        if (not traj) and isinstance(ep.get("phase_results"), dict):
            pr = ep.get("phase_results") or {}
            for k in ("G3", "G2"):
                t2 = (pr.get(k) or {}).get("trajectory", [])
                if isinstance(t2, list) and t2:
                    traj = t2
                    break
        entry = _first_dock_entry_step(traj if isinstance(traj, list) else [])
        if not entry:
            missing += 1
            continue

        x_rel = _safe_float(entry.get("x_rel"))
        y_rel = _safe_float(entry.get("y_rel"))
        psi_rel = _safe_float(entry.get("psi_rel_deg"))
        d_rel = _safe_float(entry.get("dist"))

        # 旧日志fallback：用 target_position + ref_yaw_deg 反算
        if x_rel is None or y_rel is None or psi_rel is None:
            tp = ep.get("target_position") or {}
            ego_x = _safe_float(entry.get("x"))
            ego_y = _safe_float(entry.get("y"))
            ego_yaw = _safe_float(entry.get("yaw"))
            tgt_x = _safe_float(tp.get("x"))
            tgt_y = _safe_float(tp.get("y"))
            ref_yaw = _safe_float(entry.get("ref_yaw_deg"))
            if None not in (ego_x, ego_y, ego_yaw, tgt_x, tgt_y, ref_yaw):
                x_rel, y_rel, psi_rel = _compute_rel_from_pos_yaw(
                    ego_x=float(ego_x),
                    ego_y=float(ego_y),
                    ego_yaw_deg=float(ego_yaw),
                    tgt_x=float(tgt_x),
                    tgt_y=float(tgt_y),
                    ref_yaw_deg=float(ref_yaw),
                )
            else:
                missing += 1
                continue

        entered_from_front = (x_rel < -float(args.x_front_thresh))
        # lane_misalignment：8m success but 4m fail（统一口径 min-dist）
        lane_misalignment = bool(ev.get("navsucc8")) and (not bool(ev.get("navsucc4")))

        rows.append(
            {
                "episode": ep.get("episode"),
                "scene_id": ep.get("scene_id", ep.get("scen_id")),
                "run_id": ep.get("run_id"),
                "x_rel": x_rel,
                "y_rel": y_rel,
                "psi_rel_deg": psi_rel,
                "d_rel": d_rel,
                "entered_from_front": entered_from_front,
                "lane_misalignment": lane_misalignment,
                "navsucc8": bool(ev.get("navsucc8")),
                "navsucc4": bool(ev.get("navsucc4")),
            }
        )

    # 统计条件概率
    def _cond_prob(front: bool) -> Tuple[int, int, float]:
        subset = [r for r in rows if bool(r["entered_from_front"]) == front and bool(r["navsucc8"])]
        n = len(subset)
        k = sum(1 for r in subset if bool(r["lane_misalignment"]))
        p = (k / n) if n > 0 else 0.0
        return k, n, p

    kf, nf, pf = _cond_prob(True)
    kr, nr, pr = _cond_prob(False)

    # x_rel 分布（只看 navsucc8==True 的集合，和 lane_misalignment 的集合）
    bins_all: Dict[str, int] = {}
    bins_mis: Dict[str, int] = {}
    for r in rows:
        if not bool(r["navsucc8"]):
            continue
        b = _bin_xrel(float(r["x_rel"]))
        bins_all[b] = bins_all.get(b, 0) + 1
        if bool(r["lane_misalignment"]):
            bins_mis[b] = bins_mis.get(b, 0) + 1

    md: List[str] = []
    md.append("## Dock-Entry 结构性分析（Step 3.2）")
    md.append("")
    md.append(f"- 输入日志：`{in_path.as_posix()}`")
    md.append(f"- 总行数：**{len(eps)}**；有效 entry 样本：**{len(rows)}**；缺失/无法解析：**{missing}**")
    md.append(f"- entered_from_front 判定：`x_rel < -{float(args.x_front_thresh):.2f}`（注意：x_rel<0 表示在目标前方）")
    md.append("")
    md.append("### 条件概率表（navsucc8==True 的集合里）")
    md.append("")
    md.append("| Group | #lane_misalignment | #navsucc8 | P(lane_misalignment | group) |")
    md.append("|---|---:|---:|---:|")
    md.append(f"| entered_from_front | {kf} | {nf} | {pf*100:.1f}% |")
    md.append(f"| entered_from_rear | {kr} | {nr} | {pr*100:.1f}% |")
    md.append("")
    md.append("### x_rel 分箱分布（navsucc8==True）")
    md.append("")
    md.append("| x_rel bin | count(all navsucc8) | count(lane_misalignment) |")
    md.append("|---|---:|---:|")
    for b in ["< -5", "[-5,-2)", "[-2,0)", "[0,1)", "[1,2)", "[2,5)", ">= 5"]:
        md.append(f"| {b} | {bins_all.get(b, 0)} | {bins_mis.get(b, 0)} |")
    md.append("")

    out_md = Path(args.output_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"[OK] wrote md : {out_md}")

    # 可选：画直方图（如果有matplotlib）
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        print("[WARN] matplotlib not available, skip png")
        return

    xs_all = [float(r["x_rel"]) for r in rows if bool(r["navsucc8"])]
    xs_mis = [float(r["x_rel"]) for r in rows if bool(r["lane_misalignment"])]
    if not xs_all:
        print("[WARN] no xs_all, skip png")
        return

    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    ax.hist(xs_all, bins=30, alpha=0.55, label="navsucc8==True")
    if xs_mis:
        ax.hist(xs_mis, bins=30, alpha=0.55, label="lane_misalignment (8m ok, 4m fail)")
    ax.axvline(float(args.x_front_thresh), color="red", linestyle="--", linewidth=1.0, label="front_thresh")
    ax.set_xlabel("x_rel at Dock entry (m)  [>0 means behind]")
    ax.set_ylabel("Count")
    ax.grid(alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    out_png = Path(args.output_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)
    print(f"[OK] wrote png: {out_png}")


if __name__ == "__main__":
    main()


