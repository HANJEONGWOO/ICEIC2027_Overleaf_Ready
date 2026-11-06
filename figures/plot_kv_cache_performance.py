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
from decimal import Decimal, ROUND_HALF_UP

import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from performance_pptx import write_native_pptx

HERE = Path(__file__).resolve().parent
PLACEMENT = 'Boundary'
METHODS = ('Lloyd–Max K8', 'PU-K8')
COLORS = ('#D7DADD', '#4472C4')  # Gray baseline and PowerPoint-style blue.
EDGES = ('#777777', '#4472C4')
INK, SECONDARY, GRID = '#222222', '#555555', '#DDDDDD'
W, H = 248.4, 114.0  # 3.45-inch single-column width; all scene units are points.
SCENE = {
    'width': W, 'height': H, 'font': 'Arial',
    'title': 'Boundary-placement performance and reference-window PPL',
    'subject': 'Measured KV-cache codec performance; editable bar chart',
    'shapes': [],
}

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


def rect(x, y, w, h, fill, stroke=None, lw=.4):
    SCENE['shapes'].append(dict(type='rect', x=x, y=y, w=w, h=h,
                                fill=fill, stroke=stroke, lw=lw))


def line(x1, y1, x2, y2, color=INK, lw=.4):
    SCENE['shapes'].append(dict(type='line', points=[[x1, y1], [x2, y2]],
                                stroke=color, lw=lw))


def text(x, y, w, h, label, size=7, align='center', color=INK, bold=False):
    SCENE['shapes'].append(dict(type='text', x=x, y=y, w=w, h=h, text=label,
                                size=size, color=color, bold=bold,
                                align=align, valign='middle'))


# A simple legend; every item stays independently editable in PowerPoint.
rect(62, 7.6, 7.5, 5.6, COLORS[0], EDGES[0])
text(73.5, 5.5, 55, 10, 'Lloyd–Max K8', 7.2, 'left')
rect(135, 7.6, 7.5, 5.6, COLORS[1], EDGES[1])
text(146.5, 5.5, 57, 10, 'PU-K8 (ours)', 7.2, 'left')

# All axes start at zero; the PPL axis is limited to 30 for this comparison.
PANELS = (
    ('TTFT', 'TTFT', '↓', 900, (0, 300, 600, 900), 1),
    ('Prefill', 'Prefill', '↑', 2400, (0, 800, 1600, 2400), 0),
    ('Decode', 'Decode', '↑', 45, (0, 15, 30, 45), 2),
    ('PPL', 'PPL', '↓', 30, (0, 10, 20, 30), 2),
)
AXIS_LEFT = (18, 82, 145, 208)
AXIS_WIDTH, TOP, BOTTOM = 38, 45, 106
BAR_WIDTH = 10.8
PPTX_PANELS = []

for left, (metric, title, direction, maximum, ticks, precision) in zip(AXIS_LEFT, PANELS):
    if metric == 'PPL':
        values = [Decimal(quality[PLACEMENT, method]['ppl']) for method in METHODS]
    else:
        values = [Decimal(timing[metric, PLACEMENT, method]['mean']) for method in METHODS]
    assert all(0 < value < maximum for value in values)
    PPTX_PANELS.append(dict(metric=metric, values=values, maximum=maximum,
                            tick_step=ticks[1] - ticks[0], precision=precision,
                            left=left, width=AXIS_WIDTH, top=TOP, bottom=BOTTOM))

    def yp(value):
        return BOTTOM - float(value) / maximum * (BOTTOM - TOP)

    text(left - 3, 29, AXIS_WIDTH + 6, 10, f'{title} {direction}', 7.4, bold=True)

    for tick in ticks:
        y = yp(tick)
        if tick:
            line(left, y, left + AXIS_WIDTH, y, GRID, .3)
        line(left - 2, y, left, y, INK, .4)
        text(left - 19, y - 4, 15, 8, str(tick), 5.8, 'right', SECONDARY)

    # Each pair has a close, consistent gap; inter-panel gutters house y ticks.
    for index, value in enumerate(values):
        center = left + (10 if index == 0 else 28)
        top = yp(value)
        rect(center - BAR_WIDTH / 2, top, BAR_WIDTH, BOTTOM - top,
             COLORS[index], EDGES[index], .4)
        label = value.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
        # Keep grid lines from crossing the value labels.
        rect(center - 9, top - 10.5, 18, 8, '#FFFFFF')
        text(center - 12, top - 10.5, 24, 8,
             f'{label:.{precision}f}', 6.5)

    line(left, TOP, left, BOTTOM, INK, .45)
    line(left, BOTTOM, left + AXIS_WIDTH, BOTTOM, INK, .45)


def render():
    # Liberation Sans and Arial share metrics; embed TrueType fonts in the PDF.
    for font_path in font_manager.findSystemFonts():
        font_manager.fontManager.addfont(str(font_path))
    font_manager.findfont('Liberation Sans', fallback_to_default=False)
    plt.rcParams.update({'font.family': 'Liberation Sans', 'pdf.fonttype': 42,
                         'ps.fonttype': 42, 'savefig.facecolor': 'white'})
    fig = plt.figure(figsize=(W / 72, H / 72))
    ax = fig.add_axes((0, 0, 1, 1), xlim=(0, W), ylim=(H, 0))
    ax.axis('off')
    for zorder, s in enumerate(SCENE['shapes'], start=1):
        if s['type'] == 'rect':
            ax.add_patch(Rectangle((s['x'], s['y']), s['w'], s['h'],
                                  facecolor=s['fill'], edgecolor=s['stroke'] or 'none',
                                  linewidth=s['lw'], zorder=zorder))
        elif s['type'] == 'line':
            p, q = s['points']
            ax.plot([p[0], q[0]], [p[1], q[1]], color=s['stroke'],
                    linewidth=s['lw'], solid_capstyle='butt', zorder=zorder)
        else:
            align = s['align']
            x = s['x'] + {'left': 0, 'center': .5, 'right': 1}[align] * s['w']
            ax.text(x, s['y'] + s['h'] / 2, s['text'], ha=align, va='center',
                    fontsize=s['size'], color=s['color'],
                    fontweight='bold' if s['bold'] else 'normal', zorder=zorder)
    for extension in ('pdf', 'png'):
        metadata = {'Creator': 'Matplotlib; editable vector chart', 'Title': SCENE['title']}
        if extension == 'pdf':
            metadata.update(CreationDate=None, ModDate=None)
        fig.savefig(HERE / f'kv_cache_performance.{extension}', dpi=400, metadata=metadata)
    plt.close(fig)
    write_native_pptx(SCENE, PPTX_PANELS, HERE / 'kv_cache_performance.pptx', COLORS, EDGES)
    print('Created Fig. 2 PDF / PNG / native-chart PPTX; original means and PPL preserved.')


if __name__ == '__main__':
    render()
