#!/usr/bin/env python3
"""Rebuild Fig. 4 with the shared Fig. 2 style and native PowerPoint charts.

Run: python figures/plot_kv_cache_uniform_comparison.py
Requires figures/requirements.txt and Liberation Sans TrueType fonts.
No experiments are run. Timing uses original means from three measured runs
under Odd placement, with 897 prompt and 128 generated tokens. SD is retained
in the CSV but not plotted. PPL is the aggregate over the separate four-document
set B (4092 targets per method), not the reference-window PPL.
Only printed labels are rounded; charts and embedded workbooks retain source
precision. Outputs: vector PDF, PNG and PPTX with four native editable charts.
"""
from pathlib import Path
import csv
from decimal import Decimal

from comparison_figure import render_comparison


HERE = Path(__file__).resolve().parent
METHODS = ('Uniform K8', 'PU-K8')

with (HERE / 'kv_cache_uniform_comparison.csv').open(newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
measurements = {(r['metric'], r['method']): r for r in rows}
assert len(measurements) == len(rows) == 10
assert all(r['measured_runs'] == '3' for r in rows
           if r['metric'] in ('TTFT', 'Prefill', 'Decode'))
assert all(not r['sample_sd'] and not r['measured_runs'] for r in rows
           if 'PPL' in r['metric'])

# Timing scales match Fig. 2. This separate set has PPL > 30, so its axis
# retains a 45 upper bound. Absolute PPL across datasets is not comparable.
PANELS = (
    ('TTFT', 'TTFT', '↓', 900, (0, 300, 600, 900), 1),
    ('Prefill', 'Prefill', '↑', 2400, (0, 800, 1600, 2400), 0),
    ('Decode', 'Decode', '↑', 45, (0, 15, 30, 45), 2),
    ('Held-out PPL', 'PPL', '↓', 45, (0, 15, 30, 45), 2),
)


def render():
    panels = [dict(
        metric=title, title=title, direction=direction, maximum=maximum,
        ticks=ticks, precision=precision,
        values=[Decimal(measurements[metric, method]['value']) for method in METHODS],
    ) for metric, title, direction, maximum, ticks, precision in PANELS]
    render_comparison(
        panels, ('Uniform K8', 'PU-K8 (ours)'), HERE / 'kv_cache_uniform_comparison',
        'Uniform versus PU-K8: Odd-placement performance and separate-set PPL',
        'Fig. 4: four native clustered column charts. Right-click a chart and choose '
        'Edit Data to edit its embedded Excel workbook. Timing values are means of '
        'three measured runs with Odd placement, 897 prompt and 128 generated tokens. '
        'PPL is from the separate four-document set B (4092 target tokens per method), '
        'not the reference windows. Data labels are rounded; the workbooks retain '
        'original measurement precision. Units: TTFT in ms; Prefill and Decode in '
        'tokens/s. CSV files remain the paper source of truth. PowerPoint edits do '
        'not automatically update the CSV or manuscript PDF.',
    )


if __name__ == '__main__':
    render()
