#!/usr/bin/env python3
"""Rebuild the NIAH answer-code extraction heatmap; no experiments are run.

Run: python figures/plot_kv_cache_niah_heatmap.py
Requires matplotlib, numpy, and Lato (matching the paper's other figures).
Input: kv_cache_niah_heatmap.csv, aggregated from the completed report_8k
cases.csv on exp/structured-k8-niah at 176013543. Source hashes and the scoring
definition are retained in kv_cache_niah_extraction_source.json.
Rows are needle insertion depths, columns are context capacities; every cell
contains ten cases. All panels share a fixed 0--100% red--yellow--green
color scale, without numeric annotations inside cells or a displayed colorbar.
Outputs: a vector PDF for LaTeX and a 300 dpi PNG preview.
"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import numpy as np


HERE = Path(__file__).resolve().parent
CAPACITIES = (1024, 2048, 4096, 8192)
DEPTHS = (0, 25, 50, 75, 100)
PANELS = (
    ("fp16", "FP16"),
    ("boundary_structured", "PU-K8 (ours)"),
    ("boundary_lm", "Lloyd–Max K8"),
    ("k4_v4", "TurboQuant K4/V4"),
)
TEXT = "#222831"
SECONDARY = "#66717E"


def main():
    with (HERE / "kv_cache_niah_heatmap.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    cells = {(row["group"], int(row["depth_pct"]), int(row["capacity_tokens"])): row
             for row in rows}
    expected = {(group, depth, capacity) for group, _ in PANELS
                for depth in DEPTHS for capacity in CAPACITIES}
    assert len(rows) == len(cells) == 80 and set(cells) == expected
    for row in rows:
        correct, total = int(row["correct"]), int(row["total"])
        assert total == 10 and 0 <= correct <= total
        assert float(row["accuracy_pct"]) == 100 * correct / total

    # Cross-check every column and overall result against the retained summary.
    with (HERE / "kv_cache_niah_extraction.csv").open(newline="", encoding="utf-8") as stream:
        for summary in csv.DictReader(stream):
            selected = [row for row in rows if row["group"] == summary["group"]
                        and (summary["capacity_tokens"] == "overall"
                             or row["capacity_tokens"] == summary["capacity_tokens"])]
            assert sum(int(row["correct"]) for row in selected) == int(summary["correct"])
            assert sum(int(row["total"]) for row in selected) == int(summary["total"])

    plt.rcParams.update({
        "font.family": "Lato", "font.size": 8,
        "text.color": TEXT, "axes.labelcolor": SECONDARY,
        "xtick.color": SECONDARY, "ytick.color": SECONDARY,
        "axes.linewidth": 0.4, "pdf.fonttype": 42, "ps.fonttype": 42,
        "savefig.facecolor": "white",
    })
    # Conventional NIAH heatmap: low accuracy red, intermediate yellow,
    # high accuracy green; one fixed scale for every configuration.
    cmap = plt.colormaps["RdYlGn"]
    norm = Normalize(vmin=0, vmax=100)
    # Crop the removed colorbar row while retaining the physical cell dimensions.
    figure_height = 1.77
    fig = plt.figure(figsize=(7.16, figure_height))
    for index, (group, title) in enumerate(PANELS):
        left = 0.068 + 0.230 * index
        ax = fig.add_axes((left, 0.34 / figure_height, 0.206, 1.06 / figure_height))
        values = np.array([[float(cells[group, depth, cap]["accuracy_pct"])
                            for cap in CAPACITIES] for depth in DEPTHS])
        correct = sum(int(cells[group, depth, cap]["correct"])
                      for depth in DEPTHS for cap in CAPACITIES)
        overall = 100 * correct / 200
        fig.text(left + 0.103, 1.65 / figure_height, title, ha="center", va="center",
                 fontsize=8.3, fontweight="semibold")
        fig.text(left + 0.103, 1.49 / figure_height, f"{overall:.1f}%", ha="center", va="center",
                 fontsize=7.5, color="black")
        ax.imshow(values, cmap=cmap, norm=norm, interpolation="nearest", aspect="auto")
        ax.set_xticks(range(4), ("1K", "2K", "4K", "8K"), fontsize=7.5)
        ax.set_yticks(range(5), [str(depth) for depth in DEPTHS], fontsize=7.5)
        ax.tick_params(axis="both", length=0, pad=4)
        if index == 0:
            ax.set_ylabel("Needle depth (%)", labelpad=6, fontsize=7.8)
        else:
            ax.tick_params(axis="y", labelleft=False)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_xticks(np.arange(-0.5, 4, 1), minor=True)
        ax.set_yticks(np.arange(-0.5, 5, 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=0.4)
        ax.tick_params(which="minor", length=0)

    fig.text(0.516, 0.09 / figure_height, "Context capacity (tokens)", ha="center", fontsize=7.8,
             color=SECONDARY)

    for extension in ("pdf", "png"):
        metadata = {"Creator": "Matplotlib", "Title": "NIAH answer-code extraction accuracy"}
        if extension == "pdf":
            metadata.update({"CreationDate": None, "ModDate": None})
        fig.savefig(HERE / f"kv_cache_niah_heatmap.{extension}", dpi=300, metadata=metadata)
    plt.close(fig)


if __name__ == "__main__":
    main()
