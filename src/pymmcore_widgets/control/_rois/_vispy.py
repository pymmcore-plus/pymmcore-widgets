from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from vispy import color
from vispy.scene import Compound, Markers, Polygon

if TYPE_CHECKING:
    from .roi_model import ROI


class RoiPolygon(Compound):
    """A vispy visual for the ROI."""

    def __init__(self, roi: ROI) -> None:
        self._roi = roi
        verts = np.asarray(roi.vertices)
        self._polygon = Polygon(
            pos=verts,
            color=roi.fill_color,
            border_color=roi.border_color,
            border_width=roi.border_width,
        )
        self._handles = Markers(
            pos=verts,
            size=10,
            scaling=False,  # "fixed"
            face_color=color.Color("white"),
        )
        self._handles.visible = roi.selected

        super().__init__([self._polygon, self._handles])
        self.set_gl_state(depth_test=False)

    def update_vertices(self, vertices: np.ndarray) -> None:
        """Update the vertices of the polygon."""
        self._polygon.pos = vertices
        self._handles.set_data(pos=vertices)

    def update_from_roi(self, roi: ROI) -> None:
        self._polygon.color = roi.fill_color
        self._polygon.border_color = roi.border_color
        self._polygon._border_width = roi.border_width

        self.update_vertices(roi.vertices)
        self.set_selected(roi.selected)

    def set_selected(self, selected: bool) -> None:
        self._roi.selected = selected
        self._handles.visible = selected
