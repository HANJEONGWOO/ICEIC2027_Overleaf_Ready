#!/usr/bin/env python3
"""Rebuild the combined encoder/decoder cost figure in the Fig. 2/3 style.

Run: python figures/plot_kv_cache_codec_costs.py
Requires: matplotlib and the Lato font family. No experiments are run.
Source: ai-hub-models/scripts/llm/turboquant/README.md, "Isolated codec costs".
Exact reports and input/profile hashes: kv_cache_codec_costs_sources.txt.
The CSV retains the timing and encoder named-op measurements used in the paper.
Encoder: one instrumented probe per AR128/AR1 shape on matched captured layer-0 K
inputs. AR128 represents the prefill shape; AR1 represents the generation shape.
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
measurements = {(r["component"], r["metric"], r["method"], int(r["probe_tokens"])): r
                for r in rows}
assert len(measurements) == len(rows) == 12
assert all(r["probe_count"] == "1" for r in rows)
assert all(int(r["probe_tokens"]) in ((1, 128) if r["component"] == "Encoder" else (256,))
           for r in rows)

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

# Share one legend; the three subtitles identify the distinct probe shapes.
handles = [Patch(facecolor=color, edgecolor=edge, linewidth=0.35, label=label)
           for color, edge, label in zip(COLORS, EDGES, ("Lloyd–Max K8", "PU-K8 (ours)"))]
fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 2.00 / figure_height),
           ncol=2, frameon=False, fontsize=7.0, handlelength=1.1,
           handleheight=0.75, handletextpad=0.45, columnspacing=1.6, borderaxespad=0)

panels = (
    ("Encoder", 128, "ENCODER", "AR128"),
    ("Encoder", 1, "ENCODER", "AR1"),
    ("Decoder", 256, "KV DECODER", "256 tokens"),
)
positions = (0.035, 0.370, 0.705)
bar_positions = (0.08, 0.92)
bar_width = 0.66

for left, (component, tokens, title, scope) in zip(positions, panels):
    ax = fig.add_axes((left, 0.32 / figure_height, 0.26, 0.78 / figure_height))
    original = [Decimal(measurements[component, "SDK execute", method, tokens]["value"])
                for method in METHODS[component]]
    delta = (original[1] - original[0]) / original[0] * 100
    ax.set_ylim(0, 5500)
    ax.set_xlim(-0.5, 1.5)
    ax.set_yticks([])
    ax.set_xticks([])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#C6CDD5")
    ax.spines["bottom"].set_bounds(-0.28, 1.28)
    center = left + 0.13
    fig.text(center, 1.66 / figure_height, title,
             ha="center", va="bottom", fontsize=7.2, fontweight="semibold", color=TEXT)
    fig.text(center, 1.50 / figure_height, scope,
             ha="center", va="bottom", fontsize=7.0, color=SECONDARY)
    heading = HPacker(children=[
        TextArea("SDK exec. time", textprops={"fontsize": 6.8, "color": TEXT}),
        TextArea("↓", textprops={"fontsize": 7.0, "color": "#657381"}),
    ], align="baseline", pad=0, sep=1.8)
    fig.add_artist(AnchoredOffsetbox(
        loc="lower center", child=heading, bbox_to_anchor=(center, 1.29 / figure_height),
        bbox_transform=fig.transFigure, frameon=False, pad=0, borderpad=0,
    ))
    fig.text(center, 1.15 / figure_height, "µs", ha="center", va="bottom",
             fontsize=6.8, color=SECONDARY)

    for index, value in enumerate(original):
        x = bar_positions[index]
        ax.bar(x, float(value), width=bar_width, color=COLORS[index],
               edgecolor=EDGES[index], linewidth=0.35, zorder=3)
        ax.annotate(f"{value:,.0f}", xy=(x, float(value)),
                    xytext=(0, 2.5), textcoords="offset points", ha="center", va="bottom",
                    fontsize=7.0, color=TEXT,
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
