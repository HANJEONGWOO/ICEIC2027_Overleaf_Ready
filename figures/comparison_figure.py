"""Shared single-column comparison figure and native PowerPoint chart export.

PDF/PNG use a vector scene; PPTX uses native clustered column charts with
embedded Excel workbooks. All outputs use the same original measurement values.
"""
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from performance_pptx import write_native_pptx


COLORS = ('#D7DADD', '#4472C4')  # Gray baseline and PowerPoint-style blue.
EDGES = ('#777777', '#4472C4')
INK, SECONDARY, GRID = '#222222', '#555555', '#DDDDDD'
W, H = 248.4, 114.0  # 3.45-inch single-column width; scene units are points.
AXIS_LEFT = (18, 82, 145, 208)
AXIS_WIDTH, TOP, BOTTOM = 38, 45, 106
BAR_WIDTH = 10.8


def render_comparison(panels, methods, output_stem, title, notes):
    """Render four two-method panels to PDF, PNG and editable native-chart PPTX.

    Each panel supplies metric, title, direction, maximum, ticks, precision and
    two Decimal values. Method labels are used verbatim in the shared legend
    and each embedded workbook. Notes document the figure-specific provenance.
    Only printed labels are rounded; bars and workbooks retain source precision.
    """
    assert len(panels) == 4 and len(methods) == 2
    output_stem = Path(output_stem)
    scene = {
        'width': W, 'height': H, 'font': 'Arial', 'title': title,
        'subject': 'Measured KV-cache codec performance; editable bar chart',
        'shapes': [],
    }

    def rect(x, y, w, h, fill, stroke=None, lw=.4):
        scene['shapes'].append(dict(type='rect', x=x, y=y, w=w, h=h,
                                   fill=fill, stroke=stroke, lw=lw))

    def line(x1, y1, x2, y2, color=INK, lw=.4):
        scene['shapes'].append(dict(type='line', points=[[x1, y1], [x2, y2]],
                                   stroke=color, lw=lw))

    def text(x, y, w, h, label, size=7, align='center', color=INK, bold=False):
        scene['shapes'].append(dict(type='text', x=x, y=y, w=w, h=h, text=label,
                                   size=size, color=color, bold=bold,
                                   align=align, valign='middle'))

    # A simple legend; every item stays independently editable in PowerPoint.
    rect(62, 7.6, 7.5, 5.6, COLORS[0], EDGES[0])
    text(73.5, 5.5, 55, 10, methods[0], 7.2, 'left')
    rect(135, 7.6, 7.5, 5.6, COLORS[1], EDGES[1])
    text(146.5, 5.5, 57, 10, methods[1], 7.2, 'left')

    pptx_panels = []
    for left, panel in zip(AXIS_LEFT, panels):
        metric, heading = panel['metric'], panel['title']
        direction, maximum = panel['direction'], panel['maximum']
        ticks, precision, values = panel['ticks'], panel['precision'], panel['values']
        assert len(values) == 2 and all(isinstance(v, Decimal) for v in values)
        assert all(0 < value < maximum for value in values)
        assert ticks[0] == 0 and ticks[-1] == maximum
        step = ticks[1] - ticks[0]
        assert step > 0 and all(b - a == step for a, b in zip(ticks, ticks[1:]))
        pptx_panels.append(dict(metric=metric, values=values, maximum=maximum,
                                tick_step=step, precision=precision, left=left,
                                width=AXIS_WIDTH, top=TOP, bottom=BOTTOM))

        def yp(value):
            return BOTTOM - float(value) / maximum * (BOTTOM - TOP)

        text(left - 3, 29, AXIS_WIDTH + 6, 10, f'{heading} {direction}', 7.4, bold=True)

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
            text(center - 12, top - 10.5, 24, 8, f'{label:.{precision}f}', 6.5)

        line(left, TOP, left, BOTTOM, INK, .45)
        line(left, BOTTOM, left + AXIS_WIDTH, BOTTOM, INK, .45)

    # Liberation Sans and Arial share metrics; embed TrueType fonts in the PDF.
    for font_path in font_manager.findSystemFonts():
        font_manager.fontManager.addfont(str(font_path))
    font_manager.findfont('Liberation Sans', fallback_to_default=False)
    plt.rcParams.update({'font.family': 'Liberation Sans', 'pdf.fonttype': 42,
                         'ps.fonttype': 42, 'savefig.facecolor': 'white'})
    fig = plt.figure(figsize=(W / 72, H / 72))
    ax = fig.add_axes((0, 0, 1, 1), xlim=(0, W), ylim=(H, 0))
    ax.axis('off')
    for zorder, shape in enumerate(scene['shapes'], start=1):
        if shape['type'] == 'rect':
            ax.add_patch(Rectangle((shape['x'], shape['y']), shape['w'], shape['h'],
                                  facecolor=shape['fill'],
                                  edgecolor=shape['stroke'] or 'none',
                                  linewidth=shape['lw'], zorder=zorder))
        elif shape['type'] == 'line':
            p, q = shape['points']
            ax.plot([p[0], q[0]], [p[1], q[1]], color=shape['stroke'],
                    linewidth=shape['lw'], solid_capstyle='butt', zorder=zorder)
        else:
            align = shape['align']
            x = shape['x'] + {'left': 0, 'center': .5, 'right': 1}[align] * shape['w']
            ax.text(x, shape['y'] + shape['h'] / 2, shape['text'], ha=align, va='center',
                    fontsize=shape['size'], color=shape['color'],
                    fontweight='bold' if shape['bold'] else 'normal', zorder=zorder)
    for extension in ('pdf', 'png'):
        metadata = {'Creator': 'Matplotlib; editable vector chart', 'Title': scene['title']}
        if extension == 'pdf':
            metadata.update(CreationDate=None, ModDate=None)
        fig.savefig(output_stem.with_suffix('.' + extension), dpi=400, metadata=metadata)
    plt.close(fig)
    write_native_pptx(scene, pptx_panels, output_stem.with_suffix('.pptx'),
                      COLORS, EDGES, methods, notes)
