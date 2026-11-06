#!/usr/bin/env python3
"""Rebuild Fig. 2 as a compact academic bar chart and editable PowerPoint.

Run: python figures/plot_kv_cache_performance.py
Requires matplotlib, python-pptx >= 1.0.2 and Liberation Sans TrueType fonts.
No inference is run.
Timing: original means from ten measured sessions per method; SD is not plotted.
PPL: one evaluation per reused reference window (4092 targets), without SD.
Only Boundary rows are plotted; the Odd source data remain unchanged.
Bar heights use the original precision; text alone is rounded.
PDF/PNG use the vector scene; PPTX uses four native PowerPoint charts with
embedded Excel workbooks. Both exports use the same measured data and styles.
"""
from pathlib import Path
import csv
from decimal import Decimal

from comparison_figure import render_comparison


HERE = Path(__file__).resolve().parent
PLACEMENT = 'Boundary'
METHODS = ('Lloyd–Max K8', 'PU-K8')
DISPLAY_METHODS = ('Lloyd–Max K8', 'PU-K8 (ours)')

with (HERE / 'kv_cache_performance.csv').open(newline='', encoding='utf-8') as f:
    timing_rows = list(csv.DictReader(f))
timing = {(r['metric'], r['placement'], r['method']): r for r in timing_rows}
assert len(timing) == len(timing_rows) == 12
assert all(int(r['sessions']) == 10 for r in timing_rows)
with (HERE / 'kv_cache_reference_ppl.csv').open(newline='', encoding='utf-8') as f:
    quality_rows = list(csv.DictReader(f))
quality = {(r['placement'], r['method']): r for r in quality_rows}
assert len(quality) == len(quality_rows) == 2
assert all(int(r['reference_windows']) == 4 and int(r['scored_targets']) == 4092
           for r in quality_rows)

# All axes start at zero; the PPL axis is limited to 30 for this comparison.
PANEL_SPECS = (
    ('TTFT', 'TTFT', '↓', 900, (0, 300, 600, 900), 1),
    ('Prefill', 'Prefill', '↑', 2400, (0, 800, 1600, 2400), 0),
    ('Decode', 'Decode', '↑', 45, (0, 15, 30, 45), 2),
    ('PPL', 'PPL', '↓', 30, (0, 10, 20, 30), 2),
)
PANELS = []
for metric, title, direction, maximum, ticks, precision in PANEL_SPECS:
    if metric == 'PPL':
        values = [Decimal(quality[PLACEMENT, method]['ppl']) for method in METHODS]
    else:
        values = [Decimal(timing[metric, PLACEMENT, method]['mean']) for method in METHODS]
    PANELS.append(dict(metric=metric, title=title, direction=direction,
                       maximum=maximum, ticks=ticks, precision=precision, values=values))

NOTES = (
    'Fig. 2: four native clustered column charts. Right-click a chart and choose '
    'Edit Data to edit its embedded Excel workbook. Timing values are means of '
    '10 runs; PPL is from the reference windows. Data labels are rounded, while '
    'the workbooks retain original measurement precision. Units: TTFT in ms; '
    'Prefill and Decode in tokens/s. CSV files remain the paper source of truth. '
    'PowerPoint edits do not automatically update the CSV or manuscript PDF.')


if __name__ == '__main__':
    render_comparison(PANELS, DISPLAY_METHODS, HERE / 'kv_cache_performance',
                      'Boundary-placement performance and reference-window PPL', NOTES)
    print('Created Fig. 2 PDF / PNG / native-chart PPTX; original means and PPL preserved.')
