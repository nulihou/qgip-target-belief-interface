#!/usr/bin/env python3
"""Generate a manuscript figure mapping protocols to claim-level evidence coverage."""

from __future__ import annotations

import csv
import textwrap
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
FIGS = ROOT / "08_paper_ready_outputs" / "figures"
MANUSCRIPT_FIGS = ROOT / "01_manuscript" / "paper_picture"

REGISTRY = SOURCE / "simulation_protocol_registry.csv"
CLAIMS = SOURCE / "claim_evidence_matrix.csv"
STAT_AUDIT = SOURCE / "statistical_claim_audit.csv"
PRE_GATE = SOURCE / "pre_real_robot_gate_audit.csv"
SAFETY_CASE = SOURCE / "safety_case_claim_graph.csv"

OUT_SOURCE = SOURCE / "fig_evidence_coverage_matrix_source.csv"
FIGURE_ID = "fig_evidence_coverage_matrix"


mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 6,
        "axes.labelsize": 6,
        "xtick.labelsize": 5.5,
        "ytick.labelsize": 5.5,
        "legend.fontsize": 5.5,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
    }
)


CLAIM_AXES = [
    ("odd_split", "ODD /\nsplit"),
    ("target_consistency", "target\nconsistency"),
    ("finite_sample_safety", "finite-sample\nsafety"),
    ("uncertainty_response", "uncertainty\nresponse"),
    ("reproducibility", "reproducibility /\nprovenance"),
]


FAMILIES = [
    {
        "family_id": "split_odd",
        "label": "ODD and split control",
        "protocols": ("split_audit",),
        "strengths": {"odd_split": 3, "target_consistency": 0, "finite_sample_safety": 0, "uncertainty_response": 0, "reproducibility": 1},
        "scope": "train=4050, validation=450, held-out test=500; zero pairwise split overlap",
        "boundary": "file-level split audit, not unrestricted deployment generalization",
    },
    {
        "family_id": "nominal_benchmark",
        "label": "Nominal and blackout benchmarks",
        "protocols": ("main300_blackout_benchmark", "main1000_nominal_sanity"),
        "strengths": {"odd_split": 1, "target_consistency": 1, "finite_sample_safety": 2, "uncertainty_response": 1, "reproducibility": 1},
        "scope": "N=300 main benchmark and N=1000 nominal sanity check",
        "boundary": "shared conservative controller dominates completion; not the main query-guidance discriminator",
    },
    {
        "family_id": "primary_ambiguity",
        "label": "Primary ambiguity tests",
        "protocols": ("primary_fp10_ambiguity", "primary_idswitch_ambiguity"),
        "strengths": {"odd_split": 1, "target_consistency": 3, "finite_sample_safety": 1, "uncertainty_response": 1, "reproducibility": 1},
        "scope": "two N=300 paired ambiguity protocols with LeaderAcc, ID switches, and paired CIs",
        "boundary": "supports target consistency, not universal route-completion superiority",
    },
    {
        "family_id": "layered_stress",
        "label": "Layered detector/timing degradation stress",
        "protocols": ("detector_timing_stress", "raw_sensor_like_stress", "boundary_ambiguity_stress"),
        "strengths": {"odd_split": 2, "target_consistency": 2, "finite_sample_safety": 2, "uncertainty_response": 1, "reproducibility": 1},
        "scope": "detector/timing N=300 checks plus object-list degradation and boundary N=100 screens",
        "boundary": "layered coverage, not a fully factorial raw-camera/LiDAR validation campaign",
    },
    {
        "family_id": "nis_diagnostics",
        "label": "NIS noise and outlier diagnostics",
        "protocols": ("nis_noise_diagnostic", "nis_outlier_diagnostic"),
        "strengths": {"odd_split": 0, "target_consistency": 1, "finite_sample_safety": 1, "uncertainty_response": 3, "reproducibility": 1},
        "scope": "N=100 QGIP episodes per NIS noise or outlier condition",
        "boundary": "closed-loop diagnostic response, not final real-sensor calibration",
    },
    {
        "family_id": "claim_statistics",
        "label": "Statistical and claim traceability",
        "protocols": ("statistical_traceability", "safety_case_claim_graph"),
        "strengths": {"odd_split": 2, "target_consistency": 2, "finite_sample_safety": 3, "uncertainty_response": 2, "reproducibility": 2},
        "scope": "36 statistical checks, 8 claim-evidence rows, and 12 safety-case nodes",
        "boundary": "processed-source audit and claim-discipline layer, not raw CARLA rerun evidence",
    },
    {
        "family_id": "artifact_reproducibility",
        "label": "Figure/table/source-data QA",
        "protocols": ("figure_table_reproduction",),
        "strengths": {"odd_split": 1, "target_consistency": 1, "finite_sample_safety": 1, "uncertainty_response": 1, "reproducibility": 3},
        "scope": "publication figure QA, table source mapping, source-data provenance, and local deposit metadata",
        "boundary": "production and provenance QA, not target-journal production review or DOI publication",
    },
]


STRENGTH_LABELS = {
    0: "not a claim support in this layer",
    1: "context or boundary support",
    2: "supporting quantitative/audit evidence",
    3: "primary direct evidence for this claim axis",
}

STRENGTH_CODES = {0: "", 1: "C", 2: "S", 3: "D"}


def mm(value: float) -> float:
    return value / 25.4


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def csv_count(path: Path) -> int:
    return len(read_csv(path))


def registry_by_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["protocol_id"]: row for row in rows}


def build_source_rows() -> list[dict[str, str]]:
    registry_rows = read_csv(REGISTRY)
    by_id = registry_by_id(registry_rows)
    source_rows: list[dict[str, str]] = []

    for family in FAMILIES:
        missing = [protocol for protocol in family["protocols"] if protocol not in by_id]
        if missing:
            raise SystemExit(f"missing protocol ids for {family['family_id']}: {missing}")
        statuses = [by_id[protocol]["status"] for protocol in family["protocols"]]
        anchors = sorted({by_id[protocol]["manuscript_anchor"] for protocol in family["protocols"]})
        for claim_id, claim_label in CLAIM_AXES:
            strength = int(family["strengths"][claim_id])
            source_rows.append(
                {
                    "panel": "a_protocol_to_claim_matrix",
                    "evidence_family_id": family["family_id"],
                    "evidence_family": family["label"],
                    "claim_axis": claim_id,
                    "claim_axis_label": claim_label.replace("\n", " "),
                    "strength_code": str(strength),
                    "strength_label": STRENGTH_LABELS[strength],
                    "cell_code": STRENGTH_CODES[strength],
                    "source_protocols": "; ".join(family["protocols"]),
                    "protocol_statuses": "; ".join(statuses),
                    "manuscript_anchors": "; ".join(anchors),
                    "quantitative_scope": family["scope"],
                    "boundary": family["boundary"],
                    "source_file": REGISTRY.name,
                }
            )

    inventory = [
        ("registered_protocols", "registered protocols", csv_count(REGISTRY), REGISTRY.name),
        ("claim_evidence_rows", "claim-evidence rows", csv_count(CLAIMS), CLAIMS.name),
        ("statistical_checks", "statistical checks", csv_count(STAT_AUDIT), STAT_AUDIT.name),
        ("pre_real_robot_gates", "pre-real-robot gates", csv_count(PRE_GATE), PRE_GATE.name),
        ("safety_case_nodes", "safety-case nodes", csv_count(SAFETY_CASE), SAFETY_CASE.name),
    ]
    for item_id, label, count, source_file in inventory:
        source_rows.append(
            {
                "panel": "b_evidence_inventory",
                "evidence_family_id": item_id,
                "evidence_family": label,
                "claim_axis": "inventory_count",
                "claim_axis_label": "machine-readable rows",
                "strength_code": str(count),
                "strength_label": "count of current machine-readable rows",
                "cell_code": str(count),
                "source_protocols": "",
                "protocol_statuses": "PASS",
                "manuscript_anchors": "",
                "quantitative_scope": f"{count} rows",
                "boundary": "inventory count supports traceability; it is not new experimental evidence",
                "source_file": source_file,
            }
        )
    return source_rows


def write_source(rows: list[dict[str, str]]) -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    with OUT_SOURCE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def wrap_label(label: str, width: int = 22) -> str:
    return "\n".join(textwrap.wrap(label, width=width, break_long_words=False))


def panel_label(ax, label: str, title: str) -> None:
    ax.text(-0.08, 1.04, label, transform=ax.transAxes, fontsize=8, fontweight="bold", ha="left", va="bottom")
    ax.text(0.0, 1.04, title, transform=ax.transAxes, fontsize=7, fontweight="bold", ha="left", va="bottom")


def draw_matrix(ax, rows: list[dict[str, str]]) -> None:
    matrix_rows = [row for row in rows if row["panel"] == "a_protocol_to_claim_matrix"]
    family_ids = [family["family_id"] for family in FAMILIES]
    claim_ids = [claim_id for claim_id, _ in CLAIM_AXES]
    values = np.zeros((len(family_ids), len(claim_ids)), dtype=float)
    codes = [["" for _ in claim_ids] for _ in family_ids]
    for row in matrix_rows:
        i = family_ids.index(row["evidence_family_id"])
        j = claim_ids.index(row["claim_axis"])
        values[i, j] = float(row["strength_code"])
        codes[i][j] = row["cell_code"]

    color_by_value = {0: "#FFFFFF", 1: "#E8ECEF", 2: "#D7E6F5", 3: "#B9DDCA"}
    for i in range(len(family_ids)):
        for j in range(len(claim_ids)):
            ax.add_patch(
                Rectangle(
                    (j - 0.5, i - 0.5),
                    1.0,
                    1.0,
                    facecolor=color_by_value[int(values[i, j])],
                    edgecolor="#FFFFFF",
                    linewidth=1.1,
                )
            )
    ax.set_xlim(-0.5, len(claim_ids) - 0.5)
    ax.set_ylim(len(family_ids) - 0.5, -0.5)
    ax.set_xticks(np.arange(len(CLAIM_AXES)))
    ax.set_xticklabels([label for _, label in CLAIM_AXES], fontsize=5.3)
    ax.set_yticks(np.arange(len(FAMILIES)))
    ax.set_yticklabels([wrap_label(family["label"], 24) for family in FAMILIES], fontsize=5.25)
    ax.tick_params(axis="both", length=0)

    for spine in ax.spines.values():
        spine.set_visible(False)

    for i in range(len(family_ids)):
        for j in range(len(claim_ids)):
            if codes[i][j]:
                ax.text(j, i, codes[i][j], ha="center", va="center", fontsize=5.7, fontweight="bold", color="#111827")
    ax.text(0.0, 1.04, "Claim-support matrix", transform=ax.transAxes, fontsize=7, fontweight="bold", ha="left", va="bottom")

    handles = [
        Patch(facecolor="#E8ECEF", edgecolor="#CBD5E1", label="C context/boundary"),
        Patch(facecolor="#D7E6F5", edgecolor="#CBD5E1", label="S supporting evidence"),
        Patch(facecolor="#B9DDCA", edgecolor="#CBD5E1", label="D direct evidence"),
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.52, -0.075), ncol=3, handlelength=1.1, columnspacing=1.2)


def draw_inventory(ax, rows: list[dict[str, str]]) -> None:
    inv_rows = [row for row in rows if row["panel"] == "b_evidence_inventory"]
    labels = [row["evidence_family"] for row in inv_rows]
    values = [int(row["strength_code"]) for row in inv_rows]
    y = np.arange(len(inv_rows))
    colors = ["#6B7280", "#6B7280", "#3B6EA5", "#2C8B63", "#8A6D3B"]
    ax.barh(y, values, color=colors, edgecolor="black", linewidth=0.25, height=0.58)
    ax.set_yticks(y)
    ax.set_yticklabels([wrap_label(label, 20) for label in labels], fontsize=5.4)
    ax.invert_yaxis()
    ax.set_xlabel("machine-readable rows")
    ax.set_xlim(0, max(values) * 1.16)
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.35)
    for yy, value in zip(y, values):
        ax.text(value + max(values) * 0.02, yy, str(value), va="center", ha="left", fontsize=5.4)
    panel_label(ax, "b", "Audit inventory behind the narrative")


def save_figure(fig) -> None:
    for directory in (FIGS, MANUSCRIPT_FIGS):
        directory.mkdir(parents=True, exist_ok=True)
    for suffix in (".pdf", ".svg", ".tiff", ".png"):
        path = FIGS / f"{FIGURE_ID}{suffix}"
        if suffix == ".tiff":
            fig.savefig(path, dpi=600)
        elif suffix == ".png":
            fig.savefig(path, dpi=300)
        else:
            fig.savefig(path)
        (MANUSCRIPT_FIGS / f"{FIGURE_ID}{suffix}").write_bytes(path.read_bytes())


def main() -> None:
    rows = build_source_rows()
    write_source(rows)

    fig = plt.figure(figsize=(mm(183), mm(92)))
    ax_matrix = fig.add_subplot(111)
    draw_matrix(ax_matrix, rows)
    fig.subplots_adjust(left=0.255, right=0.985, top=0.88, bottom=0.22)
    save_figure(fig)
    plt.close(fig)

    print(OUT_SOURCE)
    for suffix in (".pdf", ".svg", ".tiff", ".png"):
        print(FIGS / f"{FIGURE_ID}{suffix}")


if __name__ == "__main__":
    main()
