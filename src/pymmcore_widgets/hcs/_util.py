from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import QMarginsF, Qt
from qtpy.QtWidgets import QGraphicsScene, QGraphicsView, QWidget

if TYPE_CHECKING:
    from qtpy.QtGui import QResizeEvent


class ResizingGraphicsView(QGraphicsView):
    """A QGraphicsView that resizes the scene to fit the view."""

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.padding = 0.05  # fraction of the bounding rect

    def resizeEvent(self, event: QResizeEvent) -> None:
        if not (scene := self.scene()):
            return
        rect = scene.itemsBoundingRect()
        xmargin = rect.width() * self.padding
        ymargin = rect.height() * self.padding
        margins = QMarginsF(xmargin, ymargin, xmargin, ymargin)
        self.fitInView(rect.marginsAdded(margins), Qt.AspectRatioMode.KeepAspectRatio)
        super().resizeEvent(event)
