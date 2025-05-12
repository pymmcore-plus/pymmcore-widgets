from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import numpy as np
import useq
from shapely.geometry import Polygon, box
from shapely.prepared import prep
from vispy.scene import Compound
from vispy.visuals import LineVisual, MarkersVisual, PolygonVisual

from .roi_model import ROI

if TYPE_CHECKING:
    from collections.abc import Sequence


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
        if type(self._roi) is ROI:
            try:
                centers = plan_polygon_tiling(
                    vertices, self._roi.fov_size, order="serpentine"
                )
            except Exception as e:
                print(e)
        else:
            pos = self._roi.create_useq_position()
            if (seq := pos.sequence) is not None and isinstance(
                (grid := seq.grid_plan), useq.GridFromEdges
            ):
                for p in grid:
                    centers.append((p.x, p.y))

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


def plan_polygon_tiling(
    poly_xy: Sequence[tuple[float, float]],
    fov: tuple[float, float],
    overlap: float = 0,
    order: Literal["serpentine", "raster"] = "serpentine",
) -> list[tuple[float, float]]:
    """
    Compute an ordered list of (x, y) stage positions that cover the polygonal ROI.

    Args:
        poly_xy: Sequence of (x, y) vertices defining a non-self-intersecting polygon.
        fov: Tuple (width, height) of the camera's field of view in the same units.
        overlap: Fractional overlap between adjacent tiles (0 <= overlap < 1).
        order: 'serpentine' for alternating scan direction, 'raster' for left-to-right each row.

    Returns
    -------
        List of (x, y) positions in acquisition order.

    Raises
    ------
        ValueError: If overlap is out of [0, 1) or the polygon is invalid.
    """
    if not 0 <= overlap < 1:
        raise ValueError("overlap must be in [0, 1)")

    poly = Polygon(poly_xy)
    if not poly.is_valid:
        raise ValueError("Invalid or self-intersecting polygon.")
    prepared_poly = prep(poly)

    # Compute grid spacing and half-extents
    w, h = fov
    dx = w * (1 - overlap)
    dy = h * (1 - overlap)
    half_w, half_h = w / 2, h / 2

    # Expand bounds to ensure full coverage
    minx, miny, maxx, maxy = poly.bounds
    minx -= half_w
    miny -= half_h
    maxx += half_w
    maxy += half_h

    # Determine grid dimensions
    n_cols = int(np.ceil((maxx - minx) / dx))
    n_rows = int(np.ceil((maxy - miny) / dy))

    # Generate center coordinates
    xs = minx + (np.arange(n_cols) + 0.5) * dx
    ys = miny + (np.arange(n_rows) + 0.5) * dy

    positions: list[tuple[float, float]] = []
    for row_idx, y in enumerate(ys):
        row_xs = (
            xs
            if order == "raster" or (order == "serpentine" and row_idx % 2 == 0)
            else xs[::-1]
        )
        for x in row_xs:
            tile = box(x - half_w, y - half_h, x + half_w, y + half_h)
            if prepared_poly.intersects(tile):
                positions.append((x, y))

    return positions
