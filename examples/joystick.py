# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "pymmcore-plus[simulate]>=0.17.3",
#     "pymmcore-widgets[pyqt6]",
# ]
#
# [tool.uv.sources]
# pymmcore-widgets = { path = "../", editable = true }
# ///
import math
import random

from pymmcore_plus import CMMCorePlus
from pymmcore_plus.experimental.simulate import (
    Line,
    Point,
    Rectangle,
    Sample,
)
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ImagePreview
from pymmcore_widgets.control import StageJoystick

random.seed(42)
objects: list = []

# Grid of points across a large area
for x in range(-2000, 2001, 200):
    for y in range(-2000, 2001, 200):
        r = random.uniform(2, 8)
        intensity = random.randint(80, 255)
        objects.append(Point(x, y, intensity=intensity, radius=r))

# Radial spokes from the origin
for angle_deg in range(0, 360, 15):
    angle = math.radians(angle_deg)
    length = random.uniform(500, 1500)
    x2 = length * math.cos(angle)
    y2 = length * math.sin(angle)
    objects.append(Line((0, 0), (x2, y2), intensity=random.randint(60, 140)))

# Concentric rings of rectangles
for ring_r in (300, 600, 900, 1200, 1500):
    n = max(6, ring_r // 100)
    for i in range(n):
        angle = 2 * math.pi * i / n
        cx = ring_r * math.cos(angle)
        cy = ring_r * math.sin(angle)
        w = random.uniform(15, 50)
        h = random.uniform(15, 50)
        objects.append(
            Rectangle(
                (cx - w / 2, cy - h / 2),
                width=w,
                height=h,
                intensity=random.randint(100, 220),
                fill=random.choice([True, False]),
            )
        )

# Scattered lines across the field
for _ in range(80):
    x1 = random.uniform(-2000, 2000)
    y1 = random.uniform(-2000, 2000)
    dx = random.uniform(-300, 300)
    dy = random.uniform(-300, 300)
    objects.append(
        Line((x1, y1), (x1 + dx, y1 + dy), intensity=random.randint(50, 180))
    )

# Diagonal grid lines
for offset in range(-2000, 2001, 250):
    objects.append(Line((offset, -2000), (offset + 2000, 2000), intensity=40))
    objects.append(Line((-2000, offset), (2000, offset + 2000), intensity=40))

# Bright landmark clusters in each quadrant
for qx, qy in [(800, 800), (-800, 800), (-800, -800), (800, -800)]:
    for _ in range(15):
        px = qx + random.gauss(0, 60)
        py = qy + random.gauss(0, 60)
        objects.append(Point(px, py, intensity=255, radius=random.uniform(3, 10)))

sample = Sample(objects)

app = QApplication([])
core = CMMCorePlus.instance()
core.loadSystemConfiguration()
core.events.XYStagePositionChanged.connect(
    lambda *args: print(f"Position changed: {args}")
)
with sample.patch(core):
    prev = ImagePreview()
    core.snapImage()
    core.startContinuousSequenceAcquisition()
    w = StageJoystick(core.getXYStageDevice(), mmcore=core)
    w.setParent(prev)
    w.resize(140, 140)
    w.show()
    prev.show()
    app.exec()
