from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import numpy as np
import useq
import useq._grid


@dataclass(eq=False)
class ROI:
    """A polygonal ROI."""

    vertices: np.ndarray = field(default_factory=list)  # type: ignore[arg-type]
    text: str = "ROI"
    selected: bool = False
    border_color: str = "#F0F66C"
    border_width: int = 2
    fill_color: str = "transparent"
    font_color: str = "yellow"
    font_size: int = 12

    fov_size: tuple[float, float] | None = None  # (width, height)
    fov_overlap: tuple[float, float] = (0.0, 0.0)  # (width, height)
    scan_order: useq.OrderMode = useq.OrderMode.row_wise_snake

    def translate(self, dx: float, dy: float) -> None:
        """Translate the ROI in place by (dx, dy)."""
        self.vertices = self.vertices + np.array([dx, dy], dtype=self.vertices.dtype)

    def __post_init__(self) -> None:
        self.vertices = np.asarray(self.vertices).astype(np.float32)
        if self.vertices.ndim != 2 or self.vertices.shape[1] != 2:
            raise ValueError("Vertices must be a 2D array of shape (n, 2)")

    _uuid: UUID = field(default_factory=uuid4, init=False, repr=False)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ROI) and self._uuid == other._uuid

    def __hash__(self) -> int:
        return hash(self._uuid)

    def bbox(self) -> tuple[float, float, float, float]:
        """Return the bounding box of this ROI.

        left, top, right, bottom
        """
        (x0, y0) = self.vertices.min(axis=0)
        (x1, y1) = self.vertices.max(axis=0)
        return float(x0), float(y0), float(x1), float(y1)

    def center(self) -> tuple[float, float]:
        """Return the center of this ROI."""
        x0, y0, x1, y1 = self.bbox()
        return (x0 + x1) / 2, (y0 + y1) / 2

    def contains(self, point: tuple[float, float]) -> bool:
        """Return True if `point` lies inside this ROI."""
        x0, y0, x1, y1 = self.bbox()
        if not (x0 <= point[0] <= x1 and y0 <= point[1] <= y1):
            return False
        return self._inner_contains(point)

    def _inner_contains(self, point: tuple[float, float]) -> bool:
        """Standard even-odd rule ray-crossing test."""
        x, y = point
        inside = False
        verts = np.asarray(self.vertices)
        n = len(verts)
        for i in range(n):
            xi, yi = verts[i]
            xj, yj = verts[(i + 1) % n]
            # edge crosses horizontal ray at y?
            if (yi > y) != (yj > y):
                # compute x coordinate of intersection
                x_int = xi + (y - yi) * (xj - xi) / (yj - yi)
                if x < x_int:
                    inside = not inside
        return inside

    def translate_vertex(self, idx: int, dx: float, dy: float) -> None:
        """Move a vertex of the ROI by (dx, dy), in place."""
        if not (0 <= idx < len(self.vertices)):
            raise IndexError("Vertex index out of range")
        self.vertices[idx] += np.array([dx, dy], dtype=self.vertices.dtype)

    def create_grid_plan(
        self,
        fov_w: float | None = None,
        fov_h: float | None = None,
        overlap: float | tuple[float, float] = 0.0,
        mode: useq.OrderMode = useq.OrderMode.row_wise_snake,
    ) -> useq.GridFromPolygon | useq.GridFromEdges | None:
        """Return a useq.AbsolutePosition object that covers the ROI."""
        if fov_w is None or fov_h is None:
            if self.fov_size is None:
                raise ValueError("fov_size must be set or fov_w and fov_h must be set")
            fov_w, fov_h = self.fov_size

        left, top, right, bottom = self.bbox()

        # if the width and the height of the roi are smaller than the fov width and
        # a single position at the center of the roi is sufficient, otherwise create a
        # grid plan that covers the roi
        if abs(right - left) > fov_w or abs(bottom - top) > fov_h:
            overlap = overlap if isinstance(overlap, tuple) else (overlap, overlap)
            if type(self) is not RectangleROI:
                if len(self.vertices) < 3:
                    return None
                try:
                    return useq.GridFromPolygon(
                        vertices=list(self.vertices),
                        fov_width=fov_w,
                        fov_height=fov_h,
                        mode=mode,
                        overlap=overlap,
                    )
                except ValueError:
                    # likely a self-intersecting polygon that cannot be scanned...
                    return None
            else:
                return useq.GridFromEdges(
                    top=top,
                    bottom=bottom,
                    left=left,
                    right=right,
                    fov_width=fov_w,
                    fov_height=fov_h,
                    mode=mode,
                    overlap=overlap,
                )
        return None

    def create_useq_position(
        self,
        fov_w: float | None = None,
        fov_h: float | None = None,
        z_pos: float = 0.0,
    ) -> useq.AbsolutePosition:
        """Return a useq.AbsolutePosition object that covers the ROI."""
        grid_plan = self.create_grid_plan(
            fov_w=fov_w, fov_h=fov_h, overlap=self.fov_overlap, mode=self.scan_order
        )
        x, y = self.center()
        pos = useq.AbsolutePosition(
            x=x, y=y, z=z_pos, name=f"{self.text} {str(id(self))[-4:]}"
        )
        if grid_plan is None:
            return pos

        return pos.model_copy(
            update={"sequence": useq.MDASequence(grid_plan=grid_plan)}
        )


@dataclass(eq=False)
class RectangleROI(ROI):
    """A rectangle ROI class."""

    def __init__(
        self,
        top_left: tuple[float, float],
        bot_right: tuple[float, float],
        **kwargs: Any,
    ) -> None:
        """Create a rectangle ROI.

        Vertices are defined in the order:
        top-left, bottom-left, bottom-right, top-right.

        Parameters
        ----------
        top_left : tuple[float, float]
            The top left corner of the rectangle.
        bot_right : tuple[float, float]
            The bottom right corner of the rectangle.
        **kwargs : Any
            Additional keyword arguments to pass to the base class.
        """
        left, top = top_left
        right, bottom = bot_right
        vertices = np.array([top_left, (left, bottom), bot_right, (right, top)])
        super().__init__(vertices=vertices, **kwargs)

    @property
    def top_left(self) -> tuple[float, float]:
        """Return the top left corner of the rectangle."""
        return self.vertices[0]  # type: ignore[no-any-return]

    @property
    def bot_right(self) -> tuple[float, float]:
        """Return the bottom right corner of the rectangle."""
        return self.vertices[2]  # type: ignore[no-any-return]

    @property
    def width(self) -> float:
        """Return the width of the rectangle."""
        return self.bot_right[0] - self.top_left[0]

    @property
    def height(self) -> float:
        """Return the height of the rectangle."""
        return self.bot_right[1] - self.top_left[1]

    def translate_vertex(self, idx: int, dx: float, dy: float) -> None:
        """Move a vertex of the rectangle by (dx, dy).

        The rectangle is resized to remain rectangular.
        The two adjacent vertices are moved along with the dragged vertex.
        """
        vs = self.vertices
        # bump the clicked corner
        vs[idx][0] += dx
        vs[idx][1] += dy
        # the “other” corner on the same vertical edge: idx ^ 1
        vs[idx ^ 1][0] += dx
        # the “other” corner on the same horizontal edge: idx ^ 3
        vs[idx ^ 3][1] += dy
