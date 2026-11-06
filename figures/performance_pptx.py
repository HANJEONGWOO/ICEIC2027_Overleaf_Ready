"""Export a comparison figure with native PowerPoint charts and Excel data.

Requires python-pptx >= 1.0.2. Bars, axes and data labels are chart elements;
only the shared legend and metric headings are standalone shapes/text.
"""
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_TICK_LABEL_POSITION, XL_TICK_MARK
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Pt


def _element(tag, **attributes):
    node = OxmlElement(tag)
    for key, value in attributes.items():
        node.set(key, str(value))
    return node


def write_native_pptx(scene, panels, path, colors, edges, methods, notes):
    prs = Presentation()
    prs.slide_width = 12192000
    scale = prs.slide_width / scene['width']
    font_scale = scale / 12700
    prs.slide_height = round(scene['height'] * scale)
    prs.core_properties.title = scene['title']
    prs.core_properties.subject = 'Native editable charts with embedded measurement workbooks'
    prs.core_properties.author = 'ICEIC 2027 paper'
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor(255, 255, 255)

    def emu(value):
        return round(value * scale)

    def color(value):
        return RGBColor.from_string(value.lstrip('#'))

    def font(target, size, fill='#222222', bold=False):
        target.name = scene['font']
        target.size = Pt(size * font_scale)
        target.bold = bold
        target.color.rgb = color(fill)

    # Shared legend and headings stay independently editable.
    for s in scene['shapes']:
        if s['type'] not in ('rect', 'text') or s['y'] >= 40:
            continue
        box = (emu(s['x']), emu(s['y']), emu(s['w']), emu(s['h']))
        if s['type'] == 'rect':
            shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, *box)
            shape.fill.solid()
            shape.fill.fore_color.rgb = color(s['fill'])
            shape.line.color.rgb = color(s['stroke'])
            shape.line.width = Pt(s['lw'] * font_scale)
            shape._element.spPr.append(_element('a:effectLst'))
            style = shape._element.find(qn('p:style'))
            if style is not None:
                shape._element.remove(style)
        else:
            shape = slide.shapes.add_textbox(*box)
            tf = shape.text_frame
            tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf.word_wrap = False
            p = tf.paragraphs[0]
            p.alignment = {'left': PP_ALIGN.LEFT, 'center': PP_ALIGN.CENTER,
                           'right': PP_ALIGN.RIGHT}[s['align']]
            p.text = s['text']
            font(p.font, s['size'], s['color'], s['bold'])

    for p in panels:
        data = CategoryChartData()
        data.categories = [p['metric']]
        for name, value in zip(methods, p['values']):
            # Keep Decimal values through chart-cache and XLSX serialization.
            data.add_series(name, [value])
        # A chart frame includes the y tick labels and an explicit inner plot.
        frame_left, frame_top, frame_width, frame_height = p['left'] - 18, 40, 58, scene['height'] - 40
        frame = slide.shapes.add_chart(
            XL_CHART_TYPE.COLUMN_CLUSTERED,
            emu(frame_left), emu(frame_top), emu(frame_width), emu(frame_height), data)
        frame.name = p['metric'] + ' — editable chart'
        chart = frame.chart
        chart.has_title = chart.has_legend = False
        font(chart.font, 6.5)
        props = _element('c:spPr')
        props.append(_element('a:noFill'))
        line = _element('a:ln')
        line.append(_element('a:noFill'))
        props.append(line)
        chart._chartSpace.insert_element_before(
            props, 'c:txPr', 'c:externalData', 'c:printSettings', 'c:userShapes', 'c:extLst')

        area = chart._chartSpace.chart.plotArea
        layout = area.find(qn('c:layout'))
        if layout is None:
            layout = _element('c:layout')
            area.insert(0, layout)
        manual = _element('c:manualLayout')
        manual.append(_element('c:layoutTarget', val='inner'))
        for mode in ('xMode', 'yMode', 'wMode', 'hMode'):
            manual.append(_element('c:' + mode, val='factor'))
        for key, value in (
            ('x', 18 / frame_width), ('y', (p['top'] - frame_top) / frame_height),
            ('w', p['width'] / frame_width), ('h', (p['bottom'] - p['top']) / frame_height)):
            manual.append(_element('c:' + key, val=value))
        layout.append(manual)

        plot = chart.plots[0]
        plot.vary_by_categories = False
        # Preserve the requested gap: about 7.2 pt for 10.8 pt-wide bars.
        plot.overlap = -67
        plot.gap_width = 85
        plot.has_data_labels = True
        labels = plot.data_labels
        labels.position = XL_LABEL_POSITION.OUTSIDE_END
        labels.show_value = True
        labels.show_category_name = labels.show_series_name = labels.show_legend_key = False
        labels.show_percentage = False
        labels.number_format = '0' if p['precision'] == 0 else '0.' + '0' * p['precision']
        labels.number_format_is_linked = False
        font(labels.font, 6.5)
        for index, series in enumerate(chart.series):
            series.format.fill.solid()
            series.format.fill.fore_color.rgb = color(colors[index])
            series.format.line.color.rgb = color(edges[index])
            series.format.line.width = Pt(.4 * font_scale)

        axis = chart.value_axis
        axis.minimum_scale, axis.maximum_scale = 0, p['maximum']
        axis.major_unit = p['tick_step']
        axis.tick_labels.number_format = '0'
        axis.tick_labels.number_format_is_linked = False
        font(axis.tick_labels.font, 5.8, '#555555')
        axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
        axis.major_tick_mark = XL_TICK_MARK.OUTSIDE
        axis.minor_tick_mark = XL_TICK_MARK.NONE
        axis.has_major_gridlines = True
        axis.has_minor_gridlines = False
        axis.major_gridlines.format.line.color.rgb = color('#DDDDDD')
        axis.major_gridlines.format.line.width = Pt(.3 * font_scale)
        axis.format.line.color.rgb = color('#222222')
        axis.format.line.width = Pt(.45 * font_scale)

        axis = chart.category_axis
        axis.tick_label_position = XL_TICK_LABEL_POSITION.NONE
        axis.major_tick_mark = axis.minor_tick_mark = XL_TICK_MARK.NONE
        axis.has_major_gridlines = axis.has_minor_gridlines = False
        axis.format.line.color.rgb = color('#222222')
        axis.format.line.width = Pt(.45 * font_scale)

    slide.notes_slide.notes_text_frame.text = notes
    prs.save(Path(path))
