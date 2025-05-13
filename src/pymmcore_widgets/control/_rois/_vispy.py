from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from vispy.scene import Compound
from vispy.visuals import LineVisual, MarkersVisual, PolygonVisual

if TYPE_CHECKING:
    from .roi_model import ROI

    pass


class RoiPolygon(Compound):
    """A vispy visual for the ROI."""

    def __init__(self, roi: ROI) -> None:
        self._roi = roi
        verts = np.asarray(roi.vertices)
        self._polygon = PolygonVisual(
            pos=verts,
            color=roi.fill_color,
            border_color=roi.border_color,
            border_width=roi.border_width,
        )
        self._handles = MarkersVisual(
            pos=verts, size=10, scaling=False, face_color="white"
        )
        self._fov_centers = MarkersVisual(scaling=False, alpha=0.2)
        self._fov_lines = LineVisual(color="#333333", width=1, connect="strip")

        self._handles.visible = roi.selected
        self._fov_lines.visible = roi.selected
        self._fov_centers.visible = roi.selected

        super().__init__(
            [self._fov_lines, self._fov_centers, self._polygon, self._handles]
        )
        self.set_gl_state(depth_test=False)
        self.update_vertices(roi.vertices)

    def update_vertices(self, vertices: np.ndarray) -> None:
        """Update the vertices of the polygon."""
        self._polygon.pos = vertices
        self._handles.set_data(pos=vertices)

        centers: list[tuple[float, float]] = []
        try:
            if (grid := self._roi.create_grid_plan()) is not None:
                for p in grid:
                    centers.append((p.x, p.y))
        except Exception as e:
            raise
            print(e)

        if centers:
            edges = []
            fovw, fovh = self._roi.fov_size
            for x, y in centers:
                L = x - fovw / 2
                R = x + fovw / 2
                T = y - fovh / 2
                B = y + fovh / 2
                edges.extend([(L, T), (R, T), (R, B), (L, B), (L, T)])
            connect = np.array((True, True, True, True, False) * len(centers))
            self._fov_centers.set_data(
                pos=np.asarray(centers),
                face_color="#666600",
                size=3,
                edge_width=0,
            )
            self._fov_lines.set_data(pos=np.asarray(edges), connect=connect, width=1)
            self._fov_centers.visible = self._roi.selected
            self._fov_lines.visible = self._roi.selected
        else:
            self._fov_centers.visible = False
            self._fov_lines.visible = False

    def update_from_roi(self, roi: ROI) -> None:
        self._polygon.color = roi.fill_color
        self._polygon.border_color = roi.border_color
        self._polygon._border_width = roi.border_width

        self.update_vertices(roi.vertices)
        self.set_selected(roi.selected)

    def set_selected(self, selected: bool) -> None:
        self._roi.selected = selected
        self._handles.visible = selected
        self._fov_lines.visible = selected
        self._fov_centers.visible = selected
