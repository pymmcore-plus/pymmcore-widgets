from __future__ import annotations

import numpy as np
from vispy.color import Color
from vispy.scene import Compound, MatrixTransform, Node
from vispy.scene.visuals import Markers, Rectangle

GREEN = "#33AA33"


class StagePositionMarker(Compound):
    """A vispy CompoundVisual for a stage-position marker (rect + symbol)."""

    def __init__(
        self,
        parent: Node,
        *,
        center: tuple[float, float] = (0, 0),
        rect_width: int = 50,
        rect_height: int = 50,
        rect_color: str = GREEN,
        rect_thickness: int = 4,
        show_rect: bool = True,
        marker_symbol: str = "++",
        marker_symbol_color: str = GREEN,
        marker_symbol_size: float = 15,
        marker_symbol_edge_width: float = 10,
        show_marker_symbol: bool = True,
    ) -> None:
        self._rect = Rectangle(
            center=center,
            width=rect_width,
            height=rect_height,
            border_width=rect_thickness,
            border_color=Color(rect_color),
            color=Color("transparent"),
        )

        self._marker = Markers(
            pos=np.array([center]),
            symbol=marker_symbol,
            face_color=Color(marker_symbol_color),
            edge_color=Color(marker_symbol_color),
            size=marker_symbol_size,
            edge_width=marker_symbol_edge_width,
            scaling=True,
        )

        super().__init__([self._marker, self._rect])

        self.parent = parent
        self._rect.visible = show_rect
        self._marker.visible = show_marker_symbol
        self.set_gl_state(depth_test=False)

    def set_rect_visible(self, show: bool) -> None:
        """Toggle the rectangle border."""
        self._rect.visible = show

    def set_marker_visible(self, show: bool) -> None:
        """Toggle the center symbol."""
        self._marker.visible = show

    def apply_transform(self, mat: np.ndarray) -> None:
        """Apply a uniform transform to both sub-visuals."""
        self.transform = MatrixTransform(matrix=mat)
