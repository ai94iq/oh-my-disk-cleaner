"""Icons drawn from SVG at the exact size and pixel ratio asked for, so they stay sharp at any scale."""

import functools
import math
import os
import re
import tempfile

from PySide6.QtCore import QByteArray, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QIconEngine,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer

from .lucide import ICONS

ICON_SIZE = QSize(16, 16)  # square icons only; the icon-text gap is the stylesheet's padding
# What the app calls an icon -> the Lucide name. Rename here, never at call sites.
ICON_NAMES = {
    "analyze": "scan-search",
    "cleanup": "brush-cleaning",
    "dups": "copy",
    "stop": "square",
    "preview": "eye",
    "clean": "trash-2",
    "find": "search-check",
    "target": "hard-drive",
    "folder": "folder-open",
}
BRAND = "#4361ee"  # the app icon's background; keep it equal to the light theme's accent


def plain_svg(name, color, opacity=1.0, pixels=24, body=None):
    """The icon's SVG; `pixels` is the physical size it is drawn at, so the stroke can land on whole pixels."""
    # Lucide strokes are 2 units on a 24-unit grid: 1.67 px at 20 px (16 px at 125%), which antialiasing
    # smears over two pixels. Round the stroke to whole device pixels instead.
    width = max(1, round(2 * pixels / 24)) * 24 / pixels
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%s" stroke-opacity="%s" '
        'stroke-width="%.3f" stroke-linecap="round" stroke-linejoin="round">%s</svg>'
        % (QColor(color).name(), opacity, width, body or ICONS[ICON_NAMES.get(name, name)])
    ).encode()


def svg_bytes(name, color, opacity=1.0, pixels=24):
    """The icon's SVG, its points moved onto device pixels when that draws it crisper."""
    return plain_svg(name, color, opacity, pixels, crisp_body(ICON_NAMES.get(name, name), pixels))


def soft_share(svg, pixels):
    """Share of inked pixels only partly covered: smeared edges are what reads as blur."""
    image = QImage(pixels, pixels, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg)).render(painter, QRectF(0, 0, pixels, pixels))
    painter.end()
    alphas = [image.pixelColor(x, y).alpha() for x in range(pixels) for y in range(pixels)]
    inked = [a for a in alphas if a]
    return sum(1 for a in inked if a < 255) / max(1, len(inked))


@functools.lru_cache(maxsize=512)
def crisp_body(lucide_name, pixels):
    """Snapping sharpens boxes but can soften diagonals (a chevron went 0.57 to 0.81 soft at
    20 px, measured): keep whichever body renders crisper at this size."""
    side = max(1, round(pixels))
    plain, snap_body = ICONS[lucide_name], snapped(lucide_name, side)
    scores = [
        soft_share(plain_svg(lucide_name, "#000", 1.0, side, body), side)
        for body in (plain, snap_body)
    ]
    return snap_body if scores[1] < scores[0] else plain


# Lucide coordinates are whole units on a 24-unit grid, so at 20 px (16 px at 125%) its lines land
# on thirds and halves of pixels and a 2 px stroke smears over 3 (Stop and Clean, user report).
# Each end point and rect edge moves to the nearest place where the rounded stroke covers whole
# pixels; curve control points and radii only scale.
_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
_TOKEN = re.compile(r"[MLHVCSQTAZmlhvcsqtaz]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?")


@functools.lru_cache(maxsize=512)
def snapped(lucide_name, pixels):
    """The glyph's SVG body with points snapped for drawing at `pixels` device pixels."""
    scale = pixels / 24
    stroke = max(1, round(2 * scale))
    half = 0.5 if stroke % 2 else 0.0

    def snap(value):
        return "%.3f" % ((math.floor(value * scale - half + 0.5) + half) / scale)

    def path(d):
        out, tokens, i = [], _TOKEN.findall(d), 0
        x = y = start_x = start_y = 0.0
        command = "M"
        while i < len(tokens):
            if tokens[i].isalpha():
                command, i = tokens[i], i + 1
            upper, relative = command.upper(), command.islower()
            count = _ARGS[upper]
            if upper == "Z":
                out.append("Z")
                x, y = start_x, start_y
                continue
            args = [float(t) for t in tokens[i : i + count]]
            i += count
            if upper == "H":
                x = x + args[0] if relative else args[0]
                out.append(f"H{snap(x)}")
            elif upper == "V":
                y = y + args[0] if relative else args[0]
                out.append(f"V{snap(y)}")
            elif upper == "A":
                end_x = x + args[5] if relative else args[5]
                end_y = y + args[6] if relative else args[6]
                radii = " ".join("%.3f" % v for v in args[:2])
                flags = " ".join(str(int(v)) for v in args[2:5])
                x, y = end_x, end_y
                out.append(f"A{radii} {flags} {snap(x)} {snap(y)}")
            else:
                points = [
                    (args[j] + (x if relative else 0), args[j + 1] + (y if relative else 0))
                    for j in range(0, count, 2)
                ]
                *controls, (x, y) = points
                text = " ".join("%.3f %.3f" % p for p in controls)
                out.append(f"{upper}{text} {snap(x)} {snap(y)}".replace(f"{upper} ", upper))
                if upper == "M":
                    start_x, start_y = x, y
                    command = "l" if relative else "L"  # further pairs after M are line-tos
        return " ".join(out)

    def element(match):
        tag, attrs = match.group(1), dict(re.findall(r'([\w-]+)="([^"]*)"', match.group(2)))
        if tag == "path":
            attrs["d"] = path(attrs["d"])
        elif tag == "line":
            for key in ("x1", "y1", "x2", "y2"):
                attrs[key] = snap(float(attrs[key]))
        elif tag == "rect":
            left, top = float(attrs.get("x", 0)), float(attrs.get("y", 0))
            right, bottom = left + float(attrs["width"]), top + float(attrs["height"])
            attrs["x"], attrs["y"] = snap(left), snap(top)
            attrs["width"] = "%.3f" % (float(snap(right)) - float(attrs["x"]))
            attrs["height"] = "%.3f" % (float(snap(bottom)) - float(attrs["y"]))
        return "<%s %s />" % (tag, " ".join(f'{k}="{v}"' for k, v in attrs.items()))

    return re.sub(r"<(\w+)\s([^>]*?)\s*/>", element, ICONS[lucide_name])


def device_origin(value, ratio):
    """A logical coordinate moved to the nearest whole device pixel, so snapping starts there."""
    return math.floor(value * ratio + 0.5) / ratio


class SvgIconEngine(QIconEngine):
    """Draws the SVG at the painter's real size and device pixel ratio; `on_color` is the checked state."""

    def __init__(self, name, color, on_color=None):
        super().__init__()
        self.name, self.color, self.on_color = name, color, on_color

    def paint(self, painter, rect, mode, state):
        color = self.on_color if state == QIcon.State.On and self.on_color else self.color
        side = min(rect.width(), rect.height())
        ratio = painter.device().devicePixelRatioF() if painter.device() else 1.0
        renderer = QSvgRenderer(
            QByteArray(
                svg_bytes(
                    self.name, color, 0.4 if mode == QIcon.Mode.Disabled else 1.0, side * ratio
                )
            )
        )
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(
            painter,
            QRectF(
                device_origin(rect.x() + (rect.width() - side) / 2, ratio),
                device_origin(rect.y() + (rect.height() - side) / 2, ratio),
                side,
                side,
            ),
        )
        painter.restore()

    def pixmap(self, size, mode, state):
        pm = QPixmap(size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        self.paint(painter, pm.rect(), mode, state)
        painter.end()
        return pm

    def clone(self):
        return SvgIconEngine(self.name, self.color, self.on_color)


def icon(name, color, on_color=None):
    """An outline icon drawn in `color`; `on_color` draws the checked state (for example on an accent fill)."""
    return QIcon(SvgIconEngine(name, color, on_color))


def chevrons(color, names=("chevron-right", "chevron-down")):
    """Paths of icon PNGs (plus @2x) in a temp folder: stylesheets take image files, not icons."""
    folder = os.path.join(tempfile.gettempdir(), "diskcleaner_qt-icons")
    os.makedirs(folder, exist_ok=True)
    paths = {}
    for name in names:
        base = os.path.join(folder, "%s-%s" % (name, QColor(color).name()[1:]))
        for suffix, side in (("", 16), ("@2x", 32)):
            image = QImage(side, side, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            QSvgRenderer(QByteArray(svg_bytes(name, color, pixels=side))).render(
                painter, QRectF(0, 0, side, side)
            )
            painter.end()
            image.save(base + suffix + ".png")
        paths[name.replace("-", "_")] = (base + ".png").replace(
            "\\", "/"
        )  # QSS wants forward slashes
    return paths


DOT_MARGIN = 1  # px of clear space around a dot, so its antialiased edge is never cut


def dot_pixmap(color, size=10, hollow=False, ratio=None):
    """A filled (or hollow) status dot of `size` px plus DOT_MARGIN all round, drawn at the device pixel ratio."""
    if ratio is None:
        screen = QGuiApplication.primaryScreen()
        ratio = screen.devicePixelRatio() if screen else 1.0
    side = math.ceil((size + 2 * DOT_MARGIN) * ratio)
    pm = QPixmap(side, side)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    box = QRectF(0, 0, size * ratio, size * ratio)
    box.moveCenter(QPointF(side / 2, side / 2))
    if hollow:
        pen = 1.5 * ratio
        p.setPen(QPen(QColor(color), pen))
        p.setBrush(Qt.BrushStyle.NoBrush)
        box = box.adjusted(pen / 2, pen / 2, -pen / 2, -pen / 2)
    else:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
    p.drawEllipse(box)
    p.end()
    pm.setDevicePixelRatio(ratio)
    return pm


def app_icon(glyph="target"):
    """The window, taskbar and bundle icon: a white glyph on a rounded brand square, drawn for each size."""
    result = QIcon()
    for side in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(side, side)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(BRAND))
        p.drawRoundedRect(QRectF(0, 0, side, side), side * 0.22, side * 0.22)
        inset = side * 0.18
        QSvgRenderer(QByteArray(svg_bytes(glyph, "#ffffff", pixels=side - 2 * inset))).render(
            p, QRectF(inset, inset, side - 2 * inset, side - 2 * inset)
        )
        p.end()
        result.addPixmap(pm)
    return result
