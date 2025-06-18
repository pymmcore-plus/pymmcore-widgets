from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cached_property
from typing import Annotated, Any
from uuid import UUID, uuid4

import numpy as np
import useq
import useq._grid
from pydantic import Field, PrivateAttr
from shapely import Polygon, box, prepared


class GridFromPolygon(useq._grid._GridPlan[useq.AbsolutePosition]):
    vertices: Annotated[
        list[tuple[float, float]],
        Field(
            min_length=3,
            description="List of points that define the polygon",
            frozen=True,
        ),
    ]

    def num_positions(self) -> int:
        """Return the number of positions in the grid."""
        if self.fov_width is None or self.fov_height is None:
            raise ValueError("fov_width and fov_height must be set")
        return len(
            self._cached_tiles(
                fov=(self.fov_width, self.fov_height), overlap=self.overlap
            )
        )

    def iter_grid_positions(
        self,
        fov_width: float | None = None,
        fov_height: float | None = None,
        *,
        order: useq.OrderMode | None = None,
    ) -> Iterator[useq.AbsolutePosition]:
        """Iterate over all grid positions, given a field of view size."""
        try:
            pos = self._cached_tiles(
                fov=(
                    fov_width or self.fov_width or 1,
                    fov_height or self.fov_height or 1,
                ),
                overlap=self.overlap,
                order=order,
            )
        except ValueError:
            pos = []
        for x, y in pos:
            yield useq.AbsolutePosition(x=x, y=y)

    @cached_property
    def poly(self) -> Polygon:
        """Return the polygon vertices as a list of (x, y) tuples."""
        return Polygon(self.vertices)

    @cached_property
    def prepared_poly(self) -> prepared.PreparedGeometry:
        """Return the prepared polygon for faster intersection tests."""
        return prepared.prep(self.poly)

    _poly_cache: dict[tuple, list[tuple[float, float]]] = PrivateAttr(
        default_factory=dict
    )

    def _cached_tiles(
        self,
        *,
        fov: tuple[float, float],
        overlap: tuple[float, float],
        order: useq.OrderMode | None = None,
    ) -> list[tuple[float, float]]:
        """Compute an ordered list of (x, y) stage positions that cover the ROI."""
        # Compute grid spacing and half-extents
        mode = useq.OrderMode(order) if order is not None else self.mode
        key = (fov, overlap, mode)

        if key not in self._poly_cache:
            w, h = fov
            dx = w * (1 - overlap[0])
            dy = h * (1 - overlap[1])
            half_w, half_h = w / 2, h / 2

            # Expand bounds to ensure full coverage
            minx, miny, maxx, maxy = self.poly.bounds
            minx -= half_w
            miny -= half_h
            maxx += half_w
            maxy += half_h

            # Determine grid dimensions
            n_cols = int(np.ceil((maxx - minx) / dx))
            n_rows = int(np.ceil((maxy - miny) / dy))

            # Generate grid positions
            positions: list[tuple[float, float]] = []
            prepared_poly = self.prepared_poly

            for r, c in mode.generate_indices(n_rows, n_cols):
                x = c + minx + (c + 0.5) * dx + half_w
                y = maxy - (r + 0.5) * dy - half_h
                tile = box(x - half_w, y - half_h, x + half_w, y + half_h)
                if prepared_poly.intersects(tile):
                    positions.append((x, y))

            self._poly_cache[key] = positions
        return self._poly_cache[key]


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
    fov_overlap: tuple[float, float] | None = None  # frac (width, height) 0..1

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
    ) -> useq._grid._GridPlan | None:
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
            if type(self) is not RectangleROI:
                if len(self.vertices) < 3:
                    return None
                return GridFromPolygon(
                    vertices=self.vertices,
                    fov_width=fov_w,
                    fov_height=fov_h,
                )
            else:
                return useq.GridFromEdges(
                    top=top,
                    bottom=bottom,
                    left=left,
                    right=right,
                    fov_width=fov_w,
                    fov_height=fov_h,
                )
        return None

    def create_useq_position(
        self,
        fov_w: float | None = None,
        fov_h: float | None = None,
        z_pos: float = 0.0,
    ) -> useq.AbsolutePosition:
        """Return a useq.AbsolutePosition object that covers the ROI."""
        grid_plan = self.create_grid_plan(fov_w=fov_w, fov_h=fov_h)
        x, y = self.center()
        pos = useq.AbsolutePosition(x=x, y=y, z=z_pos)
        if grid_plan is None:
            return pos

        return pos.model_copy(
            update={
                "sequence": useq.MDASequence(
                    grid_plan=grid_plan,
                    fov_width=fov_w,
                    fov_height=fov_h,
                )
            }
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
