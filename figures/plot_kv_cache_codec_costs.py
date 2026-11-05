#!/usr/bin/env python3
"""Rebuild the combined encoder/decoder cost figure in the Fig. 2/3 style.

Run: python figures/plot_kv_cache_codec_costs.py
Requires: matplotlib and the Lato font family. No experiments are run.
Source: ai-hub-models/scripts/llm/turboquant/README.md, "Isolated codec costs".
Exact reports and input/profile hashes: kv_cache_codec_costs_sources.txt.
The CSV retains the timing and encoder named-op measurements used in the paper.
Encoder: one instrumented AR128 probe on the same captured layer-0 K input.
Decoder: one 256-token invocation, comparing Lloyd-Max K8 LUT with PU-K8
arithmetic using identical input codes and scales. Reconstruction levels differ;
each decoder matches its own FP16 reference bit-exactly.
These are different probes, not additive components of end-to-end latency.
No repeated-run SD is available. Execution-time panels share a zero-based scale.
Only the printed relative changes are rounded; raw integer values are retained.
Outputs: kv_cache_codec_costs.pdf (vector) and .png (300 dpi preview).
"""

from pathlib import Path
import csv
from decimal import Decimal, ROUND_HALF_UP

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnchoredOffsetbox, HPacker, TextArea
from matplotlib.patches import Patch


HERE = Path(__file__).resolve().parent
COLORS = ("#D4D7DE", "#3766BD")
EDGES = ("#A7AFBC", "#2C539B")
TEXT = "#222831"
SECONDARY = "#66717E"
ACCENT_TEXT = "#244A8A"
METHODS = {
    "Encoder": ("Lloyd–Max K8", "PU-K8"),
    "Decoder": ("Lloyd–Max K8", "PU-K8"),
}

with (HERE / "kv_cache_codec_costs.csv").open(newline="", encoding="utf-8") as stream:
    rows = list(csv.DictReader(stream))
measurements = {(r["component"], r["metric"], r["method"]): r for r in rows}
assert len(measurements) == len(rows) == 10
assert all(r["probe_count"] == "1" for r in rows)
assert all(r["probe_tokens"] == ("128" if r["component"] == "Encoder" else "256") for r in rows)

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

figure_height = 2.10
fig = plt.figure(figsize=(3.45, figure_height))

# Repeat the method legend and identify the component above each panel.
for center, labels in (
    (0.25, ("Lloyd–Max K8", "PU-K8 (ours)")),
    (0.75, ("Lloyd–Max K8", "PU-K8 (ours)")),
):
    handles = [Patch(facecolor=color, edgecolor=edge, linewidth=0.35, label=label)
               for color, edge, label in zip(COLORS, EDGES, labels)]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(center, 2.04 / figure_height),
               ncol=1, frameon=False, fontsize=7.0, handlelength=1.1,
               handleheight=0.75, handletextpad=0.45, labelspacing=0.25, borderaxespad=0)

panels = (
    ("Encoder", "SDK execute", "SDK exec. time", "µs", 5500),
    ("Decoder", "SDK execute", "SDK exec. time", "µs", 5500),
)
positions = (0.07, 0.57)
bar_positions = (0.10, 0.90)
bar_width = 0.66

for left, (component, metric, title, unit, ymax) in zip(positions, panels):
    ax = fig.add_axes((left, 0.30 / figure_height, 0.36, 0.81 / figure_height))
    original = [Decimal(measurements[component, metric, method]["value"])
                for method in METHODS[component]]
    delta = (original[1] - original[0]) / original[0] * 100
    ax.set_ylim(0, ymax)
    ax.set_xlim(-0.5, 1.5)
    ax.set_yticks([])
    ax.set_xticks([])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#C6CDD5")
    ax.spines["bottom"].set_bounds(-0.28, 1.28)
    ax.text(0.5, 1.48, component.upper(), transform=ax.transAxes,
            ha="center", va="bottom", fontsize=7.4, fontweight="semibold", color=TEXT)
    heading = HPacker(children=[
        TextArea(title, textprops={"fontsize": 7.0, "color": TEXT}),
        TextArea("↓", textprops={"fontsize": 7.0, "color": "#657381"}),
    ], align="baseline", pad=0, sep=2.5)
    ax.add_artist(AnchoredOffsetbox(
        loc="lower center", child=heading, bbox_to_anchor=(0.5, 1.27),
        bbox_transform=ax.transAxes, frameon=False, pad=0, borderpad=0,
    ))
    ax.text(0.5, 1.07, unit, transform=ax.transAxes, ha="center", va="bottom",
            fontsize=6.5, color=SECONDARY)

    for index, value in enumerate(original):
        x = bar_positions[index]
        ax.bar(x, float(value), width=bar_width, color=COLORS[index],
               edgecolor=EDGES[index], linewidth=0.35, zorder=3)
        ax.annotate(f"{value:,.0f}", xy=(x, float(value)),
                    xytext=(0, 2.5), textcoords="offset points", ha="center", va="bottom",
                    fontsize=7.2, color=TEXT,
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.25}, zorder=5)

    change = delta.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    ax.text(0.5, -0.13, f"{change:+.2f}%".replace("-", "−"), transform=ax.transAxes,
            ha="center", va="top", fontsize=7.1, fontweight="semibold", color=ACCENT_TEXT)

for extension in ("pdf", "png"):
    metadata = {"Creator": "Matplotlib", "Title": "Single-probe encoder and decoder costs"}
    if extension == "pdf":
        metadata.update({"CreationDate": None, "ModDate": None})
    fig.savefig(HERE / f"kv_cache_codec_costs.{extension}", dpi=300, metadata=metadata)
plt.close(fig)
