from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from vispy.color import Color
from vispy.scene import MatrixTransform, Node
from vispy.scene.visuals import Markers, Rectangle

if TYPE_CHECKING:
    from vispy.visuals.visual import VisualView

GREEN = "#3A3"


class StagePositionMarker(Node):
    """A vispy Visual to use as stage position marker.

    Parameters
    ----------
    parent : Node
        The parent node for embedding the marker in the scene.
    center : tuple
        The center of the marker in pixels.
    rect_width : int
        The width of the rectangle in pixels.
    rect_height : int
        The height of the rectangle in pixels.
    rect_color : str
        The color of the rectangle.
    rect_thickness : int
        The thickness of the rectangle border in pixels.
    show_rect : bool
        Whether to show the rectangle.
    marker_symbol : str
        The symbol to use for the marker. This can be any of the symbols
        supported by the Markers visual: 'disc', 'arrow', 'ring', 'clobber', 'square',
        'x', 'diamond', 'vbar', 'hbar', 'cross', 'tailed_arrow', 'triangle_up',
        'triangle_down', 'star', 'cross_lines', 'o', '+', '++', 's', '-', '|', '->',
        '>', '^', 'v', '*'. By default, '++'.
    marker_symbol_color : str
        The color of the symbol.
    marker_symbol_size : int
        The size of the symbol in pixels.
    show_marker_symbol : bool
        Whether to show the symbol.
    """

    def __init__(
        self,
        parent: Node,
        *,
        center: tuple = (0, 0),
        rect_width: int = 50,
        rect_height: int = 50,
        rect_color: str = GREEN,
        rect_thickness: int = 4,
        show_rect: bool = True,
        marker_symbol: str = "++",
        marker_symbol_color: str = GREEN,
        marker_symbol_size: float = 15,
        show_marker_symbol: bool = True,
    ):
        super().__init__(parent)

        self._view_scene = parent

        self._stage_position_marker_transform: MatrixTransform = MatrixTransform()

        self._rect: Rectangle | None = None
        self._marker: Markers | None = None

        self._center = center

        self._show_rect = show_rect
        self._show_marker_symbol = show_marker_symbol

        self._rect_width = rect_width
        self._rect__height = rect_height
        self._rect_color: str = rect_color
        self._rect_thickness: int = rect_thickness

        self._marker_symbol: str = marker_symbol
        self._marker_symbol_color: str = marker_symbol_color
        self._marker_symbol_size: float = marker_symbol_size

        # rectangle
        self.show_rectangle(show_rect)

        # symbol marker
        self.show_marker(show_marker_symbol)

    # -----------------------PUBLIC METHODS-----------------------

    @property
    def center(self) -> tuple[float, float]:
        """Get the center of the marker."""
        return self._center

    @property
    def transform(self) -> MatrixTransform:
        """Get the transform of the marker."""
        return self._stage_position_marker_transform

    def bounds(
        self, axis: int, view: VisualView | None = None
    ) -> tuple[float, float] | None:
        """Return the bounds that enclose both the rectangle and the marker."""
        bounds = []

        if self._rect is not None:
            rect_bounds = self._rect.bounds(axis, view)
            if rect_bounds is not None:
                bounds.append(rect_bounds)

        if self._marker is not None:
            marker_bounds = self._marker.bounds(axis, view)
            if marker_bounds is not None:
                bounds.append(marker_bounds)

        if not bounds:
            return None

        # combine all bounds
        mins = [b[0] for b in bounds if b[0] is not None]
        maxs = [b[1] for b in bounds if b[1] is not None]

        return (min(mins), max(maxs)) if mins and maxs else None

    def delete_stage_marker(self) -> None:
        """Remove the both the rectangle and the marker from the scene."""
        if self._rect is not None:
            self._rect.parent = None
            self._rect = None
        if self._marker is not None:
            self._marker.parent = None
            self._marker = None

    def show_stage_position_marker(self, show: bool) -> None:
        """Show or hide the stage position marker as a whole."""
        self.show_rectangle(show)
        self.show_marker(show)

    def show_rectangle(self, show: bool) -> None:
        """Show or hide the rectangle."""
        # if the rectangle does not exist and show is False, do nothing
        if self._rect is None and not show:
            return
        self._show_rect = show
        # create the rectangle if it does not exist and show is True
        if self._rect is None:
            self._add_rectangle()
        # if the rectangle exists, set its parent to the view scene
        elif show:
            self._rect.parent = self._view_scene
        # if the rectangle exists and show is False, set its parent to None
        else:
            self._rect.parent = None

    def show_marker(self, show: bool) -> None:
        """Show or hide the marker."""
        # if the marker does not exist and show is False, do nothing
        if self._marker is None and not show:
            return
        self._show_marker_symbol = show
        # create the marker if it does not exist and show is True
        if self._marker is None:
            self._add_marker()
        # if the marker exists, set its parent to the view scene
        elif show:
            self._marker.parent = self._view_scene
        # if the marker exists and show is False, set its parent to None
        else:
            self._marker.parent = None

    def applyTransform(self, matrix: np.ndarray) -> None:
        """Apply a transformation to both the rectangle and the marker."""
        if self._rect is None and self._marker is None:
            return
        transform = MatrixTransform(matrix=matrix)
        self._stage_position_marker_transform = transform
        if self._rect is not None:
            self._rect.transform = transform
        if self._marker is not None:
            self._marker.transform = transform

    # -----------------------PRIVATE METHODS-----------------------

    def _delete_rectangle(self) -> None:
        """Remove the rectangle from the scene."""
        if self._rect is not None:
            self._rect.parent = None
            self._rect = None

    def _delete_marker(self) -> None:
        """Remove the marker from the scene."""
        if self._marker is not None:
            self._marker.parent = None
            self._marker = None

    def _add_rectangle(self) -> None:
        """Add the rectangle to the scene."""
        # clear the previous rectangle if it exists
        self._delete_rectangle()
        self._rect = Rectangle(
            parent=self._view_scene if self._show_rect else None,
            center=self._center,
            width=self._rect_width,
            height=self._rect__height,
            border_width=self._rect_thickness,
            border_color=Color(self._rect_color),
            color=Color("transparent"),
        )
        self._rect.set_gl_state(depth_test=False)

    def _add_marker(self) -> None:
        """Add the symbol to the scene."""
        self._delete_marker()
        self._marker = Markers(
            parent=self._view_scene if self._show_marker_symbol else None,
            pos=np.array([self._center]),
            face_color=Color(self._marker_symbol_color),
            edge_color=Color(self._marker_symbol_color),
            symbol=self._marker_symbol,
            size=self._marker_symbol_size,
            scaling=True,
        )
        self._marker.set_gl_state(depth_test=False)
