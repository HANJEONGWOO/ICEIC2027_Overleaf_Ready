"""Export the overview scene to a fully editable, vector-only PowerPoint slide.

Only Python's standard library is needed.  No PowerPoint, LibreOffice,
python-pptx, bitmap rendering, or network access is required.  Positions,
font sizes, and stroke widths use the scene's top-left coordinate system.

Usage::

    from overview_pptx import write_pptx
    write_pptx(scene, "kv_cache_overview.pptx")

    python overview_pptx.py overview_scene.json kv_cache_overview.pptx
    python overview_pptx.py --validate kv_cache_overview.pptx

Rectangles, circles, text, polygons, and polylines become native editable
DrawingML shapes.  Polylines retain every sample, so quantizer distributions
and level markers remain vectors rather than flattened preview images.
"""

from __future__ import annotations

import argparse
import json
import math
import posixpath
import re
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
    "vt": "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes",
}
for _prefix, _namespace in NS.items():
    ET.register_namespace(_prefix, _namespace)

EMU_PER_INCH = 914400
SLIDE_WIDTH_EMU = 12192000  # 13 1/3 inches, matching standard widescreen width.
REL_BASE = NS["r"] + "/"
MIME_BASE = "application/vnd.openxmlformats-officedocument."


def _tag(name: str) -> str:
    prefix, local = name.split(":", 1)
    return "{" + NS[prefix] + "}" + local


def _node(name: str, attrs: dict[str, Any] | None = None) -> ET.Element:
    return ET.Element(_tag(name), {k: str(v) for k, v in (attrs or {}).items()})


def _sub(parent: ET.Element, qualified_name: str, **attrs: Any) -> ET.Element:
    child = _node(qualified_name, attrs)
    parent.append(child)
    return child


def _xml(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _finite(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite coordinate or size: {value!r}")
    return result


def _color(value: str) -> str:
    value = str(value).lstrip("#")
    if not re.fullmatch(r"[a-fA-F0-9]{6}", value):
        raise ValueError(f"Expected a six-digit RGB color; received {value!r}")
    return value.upper()


def _fill(parent: ET.Element, color: str | None) -> None:
    if color is None:
        _sub(parent, "a:noFill")
    else:
        _sub(_sub(parent, "a:solidFill"), "a:srgbClr", val=_color(color))


def _stroke(parent: ET.Element, shape: dict[str, Any], scale: float) -> None:
    width = _finite(shape.get("lw", 1))
    if width < 0:
        raise ValueError("Stroke width must not be negative")
    line = _sub(parent, "a:ln", w=round(width * scale), cap="flat", cmpd="sng", algn="ctr")
    _fill(line, shape.get("stroke") if width > 0 else None)
    _sub(line, "a:prstDash", val="dash" if shape.get("dash", False) else "solid")
    _sub(line, "a:round")


def _transform(parent: ET.Element, x: float, y: float, w: float, h: float,
               scale: float) -> None:
    xfrm = _sub(parent, "a:xfrm")
    _sub(xfrm, "a:off", x=round(x * scale), y=round(y * scale))
    _sub(xfrm, "a:ext", cx=max(1, round(w * scale)), cy=max(1, round(h * scale)))


def _sp_tree() -> ET.Element:
    tree = _node("p:spTree")
    nv = _sub(tree, "p:nvGrpSpPr")
    _sub(nv, "p:cNvPr", id=1, name="")
    _sub(nv, "p:cNvGrpSpPr")
    _sub(nv, "p:nvPr")
    xfrm = _sub(_sub(tree, "p:grpSpPr"), "a:xfrm")
    for tag, attrs in (("a:off", {"x": 0, "y": 0}),
                       ("a:ext", {"cx": 0, "cy": 0}),
                       ("a:chOff", {"x": 0, "y": 0}),
                       ("a:chExt", {"cx": 0, "cy": 0})):
        _sub(xfrm, tag, **attrs)
    return tree


def _custom_path(parent: ET.Element, points: list[list[float]], scale: float,
                 close: bool) -> None:
    if len(points) < (3 if close else 2):
        raise ValueError("Polygons need at least three points; lines need two")
    xy = [(_finite(point[0]), _finite(point[1])) for point in points]
    xmin, ymin = min(p[0] for p in xy), min(p[1] for p in xy)
    xmax, ymax = max(p[0] for p in xy), max(p[1] for p in xy)
    _transform(parent, xmin, ymin, xmax - xmin, ymax - ymin, scale)
    geometry = _sub(parent, "a:custGeom")
    for name in ("a:avLst", "a:gdLst", "a:ahLst", "a:cxnLst"):
        _sub(geometry, name)
    _sub(geometry, "a:rect", l=0, t=0, r="w", b="h")
    path = _sub(_sub(geometry, "a:pathLst"), "a:path",
                w=max(1, round((xmax - xmin) * scale)),
                h=max(1, round((ymax - ymin) * scale)),
                fill="norm" if close else "none", stroke=1, extrusionOk=0)
    for i, (x, y) in enumerate(xy):
        cmd = _sub(path, "a:moveTo" if i == 0 else "a:lnTo")
        _sub(cmd, "a:pt", x=round((x - xmin) * scale), y=round((y - ymin) * scale))
    if close:
        _sub(path, "a:close")


def _text(shape: ET.Element, data: dict[str, Any], scene_font: str,
          scale: float) -> None:
    body = _sub(shape, "p:txBody")
    bodypr = _sub(body, "a:bodyPr", wrap="square", lIns=0, tIns=0, rIns=0, bIns=0,
                  anchor="ctr" if data.get("valign", "middle") == "middle" else "t",
                  anchorCtr=0, rtlCol=0)
    _sub(bodypr, "a:noAutofit")
    _sub(body, "a:lstStyle")
    align = {"left": "l", "center": "ctr", "right": "r"}[data.get("align", "left")]
    size = max(100, round(_finite(data["size"]) * scale / 127))
    font = str(data.get("font", scene_font))
    for line in str(data["text"]).split("\n"):
        para = _sub(body, "a:p")
        ppr = _sub(para, "a:pPr", algn=align, marL=0, marR=0, indent=0)
        _sub(_sub(ppr, "a:lnSpc"), "a:spcPct", val=100000)
        _sub(_sub(ppr, "a:spcBef"), "a:spcPts", val=0)
        _sub(_sub(ppr, "a:spcAft"), "a:spcPts", val=0)
        _sub(ppr, "a:buNone")
        run = _sub(para, "a:r")
        props = _sub(run, "a:rPr", lang="en-US", sz=size,
                     b=int(bool(data.get("bold", False))),
                     i=int(bool(data.get("italic", False))), dirty=0)
        _fill(props, data.get("color", "#000000"))
        for tag in ("a:latin", "a:ea", "a:cs"):
            _sub(props, tag, typeface=font)
        text = _sub(run, "a:t")
        text.text = line
        text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        _sub(para, "a:endParaRPr", lang="en-US", sz=size)


def _shape(data: dict[str, Any], index: int, scale: float, font: str) -> ET.Element:
    kind = data["type"]
    if kind not in {"rect", "line", "polygon", "circle", "text"}:
        raise ValueError(f"Unsupported scene primitive: {kind!r}")
    shape = _node("p:sp")
    nv = _sub(shape, "p:nvSpPr")
    name = str(data.get("name", f"{kind.capitalize()} {index}"))
    _sub(nv, "p:cNvPr", id=index, name=name)
    _sub(nv, "p:cNvSpPr", **({"txBox": 1} if kind == "text" else {}))
    _sub(nv, "p:nvPr")
    props = _sub(shape, "p:spPr")
    if kind in {"line", "polygon"}:
        _custom_path(props, data["points"], scale, close=kind == "polygon")
    else:
        if kind == "circle":
            radius = _finite(data["r"])
            if radius <= 0:
                raise ValueError("Circle radius must be positive")
            x, y = _finite(data["cx"]) - radius, _finite(data["cy"]) - radius
            w, h = 2 * radius, 2 * radius
        else:
            x, y, w, h = (_finite(data[key]) for key in ("x", "y", "w", "h"))
            if w <= 0 or h <= 0:
                raise ValueError("Rectangle and text dimensions must be positive")
        _transform(props, x, y, w, h, scale)
        _sub(_sub(props, "a:prstGeom", prst="ellipse" if kind == "circle" else "rect"),
             "a:avLst")
    _fill(props, None if kind in {"line", "text"} else data.get("fill"))
    _stroke(props, {"stroke": None, "lw": 0} if kind == "text" else data, scale)
    if kind == "text":
        _text(shape, data, font, scale)
    return shape


def _relationships(items: list[tuple[str, str, str]]) -> bytes:
    root = _node("rel:Relationships")
    for relid, reltype, target in items:
        _sub(root, "rel:Relationship", Id=relid, Type=reltype, Target=target)
    return _xml(root)


def _theme(font: str) -> bytes:
    theme = _node("a:theme", {"name": "Flat scientific overview"})
    elements = _sub(theme, "a:themeElements")
    colors = _sub(elements, "a:clrScheme", name="Overview palette")
    for name, color in (("dk1", "182230"), ("lt1", "FFFFFF"), ("dk2", "344054"),
                        ("lt2", "F8FAFC"), ("accent1", "3766BD"), ("accent2", "21816B"),
                        ("accent3", "E8EDF5"), ("accent4", "D4D7DE"), ("accent5", "BF6A3C"),
                        ("accent6", "7B61A8"), ("hlink", "3766BD"), ("folHlink", "7B61A8")):
        _sub(_sub(colors, "a:" + name), "a:srgbClr", val=color)
    fonts = _sub(elements, "a:fontScheme", name="Overview fonts")
    for tag in ("a:majorFont", "a:minorFont"):
        group = _sub(fonts, tag)
        _sub(group, "a:latin", typeface=font)
        _sub(group, "a:ea", typeface="")
        _sub(group, "a:cs", typeface="")
    fmt = _sub(elements, "a:fmtScheme", name="Flat shapes")
    fills = _sub(fmt, "a:fillStyleLst")
    for _ in range(3):
        _sub(_sub(fills, "a:solidFill"), "a:schemeClr", val="phClr")
    lines = _sub(fmt, "a:lnStyleLst")
    for width in (6350, 12700, 19050):
        line = _sub(lines, "a:ln", w=width, cap="flat", cmpd="sng", algn="ctr")
        _sub(_sub(line, "a:solidFill"), "a:schemeClr", val="phClr")
        _sub(line, "a:prstDash", val="solid")
        _sub(line, "a:miter", lim=800000)
    effects = _sub(fmt, "a:effectStyleLst")
    for _ in range(3):
        _sub(_sub(effects, "a:effectStyle"), "a:effectLst")
    backgrounds = _sub(fmt, "a:bgFillStyleLst")
    for _ in range(3):
        _sub(_sub(backgrounds, "a:solidFill"), "a:schemeClr", val="phClr")
    _sub(theme, "a:objectDefaults")
    _sub(theme, "a:extraClrSchemeLst")
    return _xml(theme)


def _content_types() -> bytes:
    root = _node("ct:Types")
    _sub(root, "ct:Default", Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
    _sub(root, "ct:Default", Extension="xml", ContentType="application/xml")
    parts = {
        "/ppt/presentation.xml": MIME_BASE + "presentationml.presentation.main+xml",
        "/ppt/slides/slide1.xml": MIME_BASE + "presentationml.slide+xml",
        "/ppt/slideMasters/slideMaster1.xml": MIME_BASE + "presentationml.slideMaster+xml",
        "/ppt/slideLayouts/slideLayout1.xml": MIME_BASE + "presentationml.slideLayout+xml",
        "/ppt/theme/theme1.xml": MIME_BASE + "theme+xml",
        "/docProps/core.xml": "application/vnd.openxmlformats-package.core-properties+xml",
        "/docProps/app.xml": MIME_BASE + "extended-properties+xml",
    }
    for part, mime in parts.items():
        _sub(root, "ct:Override", PartName=part, ContentType=mime)
    return _xml(root)


def write_pptx(scene: dict[str, Any], path: str | Path) -> Path:
    """Write one editable slide from the shared scene; return its output path."""
    width, height = _finite(scene["width"]), _finite(scene["height"])
    if min(width, height) <= 0:
        raise ValueError("Scene dimensions must be positive")
    font = str(scene.get("font", "Arial"))
    scale = SLIDE_WIDTH_EMU / width
    slide_height = round(height * scale)
    presentation = _node("p:presentation")
    _sub(_sub(presentation, "p:sldMasterIdLst"), "p:sldMasterId",
         id=2147483648, **{_tag("r:id"): "rId1"})
    _sub(_sub(presentation, "p:sldIdLst"), "p:sldId", id=256,
         **{_tag("r:id"): "rId2"})
    _sub(presentation, "p:sldSz", cx=SLIDE_WIDTH_EMU, cy=slide_height, type="custom")
    _sub(presentation, "p:notesSz", cx=6858000, cy=9144000)
    _sub(presentation, "p:defaultTextStyle")

    slide = _node("p:sld")
    content = _sub(slide, "p:cSld", name="KV cache quantization overview")
    tree = _sp_tree()
    content.append(tree)
    for i, item in enumerate(scene["shapes"], start=2):
        tree.append(_shape(item, i, scale, font))
    _sub(_sub(slide, "p:clrMapOvr"), "a:masterClrMapping")

    master = _node("p:sldMaster")
    _sub(master, "p:cSld").append(_sp_tree())
    _sub(master, "p:clrMap", bg1="lt1", tx1="dk1", bg2="lt2", tx2="dk2",
         accent1="accent1", accent2="accent2", accent3="accent3", accent4="accent4",
         accent5="accent5", accent6="accent6", hlink="hlink", folHlink="folHlink")
    _sub(_sub(master, "p:sldLayoutIdLst"), "p:sldLayoutId", id=2147483649,
         **{_tag("r:id"): "rId1"})
    txstyles = _sub(master, "p:txStyles")
    for name in ("p:titleStyle", "p:bodyStyle", "p:otherStyle"):
        _sub(_sub(txstyles, name), "a:lvl1pPr", algn="l")

    layout = _node("p:sldLayout", {"type": "blank", "preserve": 1})
    _sub(layout, "p:cSld", name="Blank").append(_sp_tree())
    _sub(_sub(layout, "p:clrMapOvr"), "a:masterClrMapping")

    core = _node("cp:coreProperties")
    _sub(core, "dc:title").text = str(scene.get("title", "KV cache quantization overview"))
    _sub(core, "dc:subject").text = "Editable vector overview with calibrated quantization levels"
    _sub(core, "dc:creator").text = "ICEIC 2027 paper"
    _sub(core, "dc:description").text = "Native editable shapes and text generated from the shared overview scene."
    app = _node("ep:Properties")
    _sub(app, "ep:Application").text = "Overview native DrawingML exporter"
    _sub(app, "ep:PresentationFormat").text = "Custom"
    _sub(app, "ep:Slides").text = "1"
    _sub(app, "ep:Notes").text = "0"
    _sub(app, "ep:HiddenSlides").text = "0"
    _sub(app, "ep:AppVersion").text = "1.0"

    parts = {
        "[Content_Types].xml": _content_types(),
        "_rels/.rels": _relationships([
            ("rId1", REL_BASE + "officeDocument", "ppt/presentation.xml"),
            ("rId2", NS["rel"] + "/metadata/core-properties", "docProps/core.xml"),
            ("rId3", REL_BASE + "extended-properties", "docProps/app.xml")]),
        "docProps/core.xml": _xml(core),
        "docProps/app.xml": _xml(app),
        "ppt/presentation.xml": _xml(presentation),
        "ppt/_rels/presentation.xml.rels": _relationships([
            ("rId1", REL_BASE + "slideMaster", "slideMasters/slideMaster1.xml"),
            ("rId2", REL_BASE + "slide", "slides/slide1.xml")]),
        "ppt/slides/slide1.xml": _xml(slide),
        "ppt/slides/_rels/slide1.xml.rels": _relationships([
            ("rId1", REL_BASE + "slideLayout", "../slideLayouts/slideLayout1.xml")]),
        "ppt/slideMasters/slideMaster1.xml": _xml(master),
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": _relationships([
            ("rId1", REL_BASE + "slideLayout", "../slideLayouts/slideLayout1.xml"),
            ("rId2", REL_BASE + "theme", "../theme/theme1.xml")]),
        "ppt/slideLayouts/slideLayout1.xml": _xml(layout),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": _relationships([
            ("rId1", REL_BASE + "slideMaster", "../slideMasters/slideMaster1.xml")]),
        "ppt/theme/theme1.xml": _theme(font),
    }
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    validate_pptx(output)
    return output


def validate_pptx(path: str | Path) -> dict[str, int]:
    """Check XML, internal relationships, shape IDs, and absence of pictures.

    This structural validation is intentionally independent of the scene.
    It does not claim to replace opening the file in Microsoft PowerPoint.
    """
    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Corrupt ZIP member in PowerPoint package")
        names = set(archive.namelist())
        if any(name.startswith("ppt/media/") for name in names):
            raise ValueError("An editable-only overview must not embed media files")
        trees = {name: ET.fromstring(archive.read(name)) for name in names
                 if name.endswith((".xml", ".rels"))}
        for name, root in trees.items():
            if name.endswith(".rels"):
                source_dir = "" if name == "_rels/.rels" else posixpath.dirname(posixpath.dirname(name))
                for relationship in root:
                    if relationship.get("TargetMode") == "External":
                        continue
                    target = posixpath.normpath(posixpath.join(source_dir, relationship.attrib["Target"]))
                    if target not in names:
                        raise ValueError(f"Missing relationship target: {name} -> {target}")
        slide = trees["ppt/slides/slide1.xml"]
        shapes = slide.findall(".//p:sp", NS)
        identifiers = [node.attrib["id"] for node in slide.findall(".//p:cNvPr", NS)]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Duplicate shape identifiers")
        pictures = slide.findall(".//p:pic", NS)
        if pictures:
            raise ValueError("The slide contains non-editable picture shapes")
        return {"xml_parts": len(trees), "editable_shapes": len(shapes), "pictures": len(pictures)}


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scene", nargs="?", type=Path, help="Scene JSON file")
    parser.add_argument("output", nargs="?", type=Path, help="Destination .pptx file")
    parser.add_argument("--validate", metavar="PPTX", type=Path, help="Validate an existing package")
    args = parser.parse_args()
    if args.validate:
        print(json.dumps(validate_pptx(args.validate)))
    elif args.scene and args.output:
        output = write_pptx(json.loads(args.scene.read_text(encoding="utf-8")), args.output)
        print(f"Wrote {output}: {json.dumps(validate_pptx(output))}")
    else:
        parser.error("provide SCENE_JSON OUTPUT_PPTX, or --validate PPTX")


if __name__ == "__main__":
    _main()
