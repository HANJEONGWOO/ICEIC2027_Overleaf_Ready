#!/usr/bin/env python3
"""Rebuild Fig. 2: Boundary performance and reference-window PPL in a compact single-column row.

Run: python figures/plot_kv_cache_performance.py
Requires: matplotlib, numpy, and the Lato font family. No device experiments are run.
Timing CSV: original means and sample SD from ten measured sessions per method;
Odd rows are retained as source data but are not plotted.
PPL CSV: aggregate PPL over four reused reference windows, evaluated once per
method/window (4092 targets). Values match Table I's full-precision source
comments in conference_101719.tex. No PPL standard deviation is available.
Bars retain original precision. Only printed values and changes are rounded.
Outputs: kv_cache_performance.pdf (vector) and .png (300 dpi preview).
"""

from pathlib import Path
import csv
from decimal import Decimal, ROUND_HALF_UP

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnchoredOffsetbox, HPacker, TextArea
from matplotlib.patches import Patch
import numpy as np


HERE = Path(__file__).resolve().parent
PLACEMENT = "Boundary"
METHODS = ("Lloyd–Max K8", "Structured K8")
# A neutral baseline and one saturated accent distinguish methods in a small
# panel; their luminance contrast also preserves the distinction in grayscale.
COLORS = ("#D4D7DE", "#3766BD")
EDGES = ("#A7AFBC", "#2C539B")
TEXT = "#222831"
SECONDARY = "#66717E"
ACCENT_TEXT = "#244A8A"

with (HERE / "kv_cache_performance.csv").open(newline="", encoding="utf-8") as stream:
    timing_rows = list(csv.DictReader(stream))
timing = {(r["metric"], r["placement"], r["method"]): r for r in timing_rows}
assert len(timing) == len(timing_rows) == 12
assert all(int(r["sessions"]) == 10 for r in timing_rows)

with (HERE / "kv_cache_reference_ppl.csv").open(newline="", encoding="utf-8") as stream:
    quality_rows = list(csv.DictReader(stream))
quality = {(r["placement"], r["method"]): r for r in quality_rows}
assert len(quality) == len(quality_rows) == 2
assert all(int(r["reference_windows"]) == 4 and int(r["scored_targets"]) == 4092
           for r in quality_rows)

plt.rcParams.update({
    "font.family": "Lato",
    "font.size": 8,
    "text.color": TEXT,
    "axes.labelcolor": TEXT,
    "xtick.color": SECONDARY,
    "ytick.color": SECONDARY,
    "axes.linewidth": 0.4,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "savefig.facecolor": "white",
})

# Reserve a separate legend row without shrinking the bars or their value labels.
figure_height = 1.74
fig = plt.figure(figsize=(3.45, figure_height))
legend = [Patch(facecolor=color, edgecolor=edge, linewidth=0.35, label=method)
          for color, edge, method in zip(COLORS, EDGES, METHODS)]
fig.legend(handles=legend, loc="upper center", bbox_to_anchor=(0.50, 0.99),
           ncol=2, frameon=False, fontsize=7.4, handlelength=1.1,
           handleheight=0.75, handletextpad=0.45, columnspacing=1.5, borderaxespad=0)

panels = (
    ("TTFT", "TTFT", "↓", "ms", 900, 1),
    ("Prefill", "PREFILL", "↑", "tokens/s", 2200, 0),
    ("Decode", "DECODE", "↑", "tokens/s", 45, 2),
    ("PPL", "PPL", "↓", "", 25, 2),
)
# Keep each method pair close, with more space between different metrics.
positions = (0.0225, 0.2675, 0.5125, 0.7575)
bar_positions = (0.10, 0.90)
bar_width = 0.66

for left, (metric, title, direction, unit, ymax, precision) in zip(positions, panels):
    # Preserve physical plot height and bottom margin when adding headroom.
    ax = fig.add_axes((left, 0.2916 / figure_height, 0.22, 0.81 / figure_height))
    if metric == "PPL":
        original = [Decimal(quality[PLACEMENT, method]["ppl"]) for method in METHODS]
        sd = None  # Aggregate PPL is not a ten-session mean; do not invent an SD.
    else:
        original = [Decimal(timing[metric, PLACEMENT, method]["mean"]) for method in METHODS]
        sd = np.array([float(timing[metric, PLACEMENT, method]["sample_sd"]) for method in METHODS])
        assert np.all(sd >= 0)
    means = np.array([float(value) for value in original])
    assert np.all(means > 0)
    delta = (original[1] - original[0]) / original[0] * 100
    if metric != "PPL":
        stored = Decimal(timing[metric, PLACEMENT, METHODS[1]]["structured_improvement_percent"])
        assert abs(abs(delta) - stored) < Decimal("0.005")

    ax.set_ylim(0, ymax)
    ax.set_xlim(-0.5, 1.5)
    # Omit numeric y ticks and grid; raw value labels supply the actual magnitudes.
    # Scales remain independent and zero-based.
    ax.set_yticks([])
    ax.set_xticks([])  # The method legend applies to every pair of bars.
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#C6CDD5")
    ax.spines["bottom"].set_bounds(-0.28, 1.28)
    heading = HPacker(children=[
        TextArea(title, textprops={"fontsize": 7.4, "fontweight": "semibold", "color": TEXT}),
        TextArea(direction, textprops={"fontsize": 7.0, "color": "#657381"}),
    ], align="baseline", pad=0, sep=2.5)
    ax.add_artist(AnchoredOffsetbox(
        loc="lower center", child=heading, bbox_to_anchor=(0.5, 1.27),
        bbox_transform=ax.transAxes, frameon=False, pad=0, borderpad=0,
    ))
    if unit:
        ax.text(0.5, 1.07, unit, transform=ax.transAxes, ha="center", va="bottom",
                fontsize=6.5, color=SECONDARY)

    for index, method in enumerate(METHODS):
        x = bar_positions[index]
        ax.bar(x, means[index], width=bar_width, color=COLORS[index],
               edgecolor=EDGES[index], linewidth=0.35, zorder=3)
        error = 0 if sd is None else sd[index]
        if sd is not None:
            ax.errorbar(x, means[index], yerr=error, fmt="none", ecolor=TEXT,
                        elinewidth=0.5, capsize=1.35, capthick=0.5, zorder=4)
        label = original[index].quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
        ax.annotate(f"{label:.{precision}f}", xy=(x, means[index] + error),
                    xytext=(0, 2.5), textcoords="offset points", ha="center", va="bottom",
                    fontsize=7.2, color=TEXT,
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.25}, zorder=5)

    change = delta.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    change_text = f"{change:+.2f}%".replace("-", "−")
    ax.text(0.5, -0.13, change_text, transform=ax.transAxes, ha="center", va="top",
            fontsize=7.1, fontweight="semibold", color=ACCENT_TEXT)

for extension in ("pdf", "png"):
    metadata = {"Creator": "Matplotlib", "Title": "Boundary-placement KV-cache performance and reference PPL"}
    if extension == "pdf":
        metadata.update({"CreationDate": None, "ModDate": None})
    fig.savefig(HERE / f"kv_cache_performance.{extension}", dpi=300, metadata=metadata)
plt.close(fig)
