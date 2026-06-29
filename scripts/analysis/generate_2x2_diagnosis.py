#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 4.2: 生成 2×2 诊断热力图（Correct/Wrong × Success/Fail）

核心原则：
- Correct/Wrong 来自 is_correct（chosen_idx_graph == target_idx_gt，或 gs_correct 字段）
- Success 有两种口径：
  1) 几何成功（Geometric Success）：navsucc@{thr} = (d_min_to_selected < thr)
  2) 语义成功（Semantic Success）：semnavsucc@{thr} = is_correct AND (d_min_to_gt < thr)

这两张图用来解释“选错也可能几何成功”的现象：Wrong&GeometricSuccess 会非零，
而 Wrong&SemanticSuccess 理论上应为 0（因为定义强绑 GT）。
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.analysis.unified_episode_evaluator import evaluate_episode  # type: ignore


@dataclass
class Confusion2x2:
    # rows: Correct, Wrong
    # cols: Success, Fail
    cc: int = 0  # correct & success
    cf: int = 0  # correct & fail
    wc: int = 0  # wrong & success
    wf: int = 0  # wrong & fail

    @property
    def total(self) -> int:
        return self.cc + self.cf + self.wc + self.wf

    def as_matrix(self) -> List[List[int]]:
        return [[self.cc, self.cf], [self.wc, self.wf]]

    def as_percent_matrix(self) -> List[List[float]]:
        n = max(1, self.total)
        return [[100.0 * self.cc / n, 100.0 * self.cf / n],
                [100.0 * self.wc / n, 100.0 * self.wf / n]]


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


def _confusion_2x2(evaluated: List[Dict[str, Any]], success_key: str) -> Confusion2x2:
    c = Confusion2x2()
    for r in evaluated:
        correct = bool(r.get("is_correct", False))
        success = bool(r.get(success_key, False))
        if correct and success:
            c.cc += 1
        elif correct and (not success):
            c.cf += 1
        elif (not correct) and success:
            c.wc += 1
        else:
            c.wf += 1
    return c


def _write_md(path: Path, title: str, rows: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([f"## {title}", ""] + rows + [""]), encoding="utf-8")


def _format_md_table(c: Confusion2x2) -> List[str]:
    p = c.as_percent_matrix()
    # 行：Correct/Wrong；列：Success/Fail
    return [
        f"- total: **{c.total}**",
        "",
        "|  | Success | Fail |",
        "|---|---:|---:|",
        f"| Correct | {c.cc} ({p[0][0]:.1f}%) | {c.cf} ({p[0][1]:.1f}%) |",
        f"| Wrong | {c.wc} ({p[1][0]:.1f}%) | {c.wf} ({p[1][1]:.1f}%) |",
    ]


def _try_plot_heatmap_png(path: Path, c: Confusion2x2, title: str) -> bool:
    try:
        import matplotlib.pyplot as plt  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return False

    mat = np.array(c.as_percent_matrix())
    fig, ax = plt.subplots(figsize=(4.2, 3.2))
    im = ax.imshow(mat, cmap="Blues", vmin=0.0, vmax=max(1.0, float(mat.max())))

    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Success", "Fail"])
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Correct", "Wrong"])
    ax.set_title(title)

    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{mat[i, j]:.1f}%", ha="center", va="center", color="black", fontsize=10)

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return True


def _evaluate_jsonl(path: Path) -> List[Dict[str, Any]]:
    eps = _load_jsonl(path)
    out: List[Dict[str, Any]] = []
    for ep in eps:
        out.append(evaluate_episode(ep))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gs", type=str, required=True, help="GS jsonl")
    ap.add_argument("--random", type=str, required=True, help="Random jsonl")
    ap.add_argument("--oracle", type=str, required=True, help="Oracle jsonl")
    ap.add_argument("--out-dir", type=str, default="results/proto_main_eval/diagnosis_2x2")
    ap.add_argument("--thr", type=float, default=8.0, help="threshold meters (supports 8 or 4)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    thr = float(args.thr)
    if abs(thr - 8.0) < 1e-6:
        geo_key = "navsucc8"
        sem_key = "semnavsucc8"
        tag = "8m"
    elif abs(thr - 4.0) < 1e-6:
        geo_key = "navsucc4"
        sem_key = "semnavsucc4"
        tag = "4m"
    else:
        raise ValueError("Only thr=8 or thr=4 are supported (to match paper metrics).")

    methods = {
        "GS": Path(args.gs),
        "Random": Path(args.random),
        "Oracle": Path(args.oracle),
    }

    # 生成每个方法两张图：Geometric vs Semantic
    for name, p in methods.items():
        evaluated = _evaluate_jsonl(p)

        c_geo = _confusion_2x2(evaluated, geo_key)
        c_sem = _confusion_2x2(evaluated, sem_key)

        md_geo = out_dir / f"{name.lower()}_2x2_geometric_{tag}.md"
        md_sem = out_dir / f"{name.lower()}_2x2_semantic_{tag}.md"
        png_geo = out_dir / f"{name.lower()}_2x2_geometric_{tag}.png"
        png_sem = out_dir / f"{name.lower()}_2x2_semantic_{tag}.png"

        _write_md(md_geo, f"{name} 2×2 Diagnostic (Geometric Success @{tag})", _format_md_table(c_geo))
        _write_md(md_sem, f"{name} 2×2 Diagnostic (Semantic Success @{tag})", _format_md_table(c_sem))

        _try_plot_heatmap_png(png_geo, c_geo, f"{name} Geometric @{tag}")
        _try_plot_heatmap_png(png_sem, c_sem, f"{name} Semantic @{tag}")

    # 汇总说明（便于论文/回复审稿人复制）
    summary_md = out_dir / f"README_2x2_{tag}.md"
    summary_md.write_text(
        "\n".join(
            [
                f"## 2×2 Diagnostic Summary (@{tag})",
                "",
                "- Rows: Correct / Wrong (is_correct)",
                f"- Geometric Success: `{geo_key}` uses **selected** distance",
                f"- Semantic Success: `{sem_key}` uses **GT** distance and requires is_correct",
                "",
                "These two diagnostics clarify whether improvements come from correct target selection or accidental geometric proximity.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"[OK] wrote outputs to {out_dir}")


if __name__ == "__main__":
    main()


