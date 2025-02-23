from collections.abc import Sequence
from enum import Enum
from typing import Any

import numpy as np
import vispy.color
from vispy import scene
from vispy.app.canvas import MouseEvent


class ROIMoveMode(Enum):
    """ROI modes."""

    NONE = "none"  # No movement
    DRAW = "draw"  # Drawing a new ROI
    HANDLE = "handle"  # Moving a handle
    TRANSLATE = "translate"  # Translating the whole ROI


class ROIRectangle:
    """A rectangle ROI."""

    def __init__(self, parent: Any) -> None:
        self._selected = False
        self._move_mode: ROIMoveMode = ROIMoveMode.DRAW
        self._move_anchor: tuple[float, float] = (0, 0)

        # Rectangle handles both fill and border
        self._rect = scene.Rectangle(
            center=[0, 0],
            width=1,
            height=1,
            color=None,
            border_color=vispy.color.Color("yellow"),
            border_width=2,
            parent=parent,
        )
        # NB: Should be greater than image orders BUT NOT handle order
        self._rect.set_gl_state(depth_test=False)
        self._rect.interactive = True

        self._handle_data = np.zeros((4, 2))
        self._handle_size = 10  # px
        self._handles = scene.Markers(
            pos=self._handle_data,
            size=self._handle_size,
            scaling=False,  # "fixed"
            face_color=vispy.color.Color("white"),
            parent=parent,
        )
        # NB: Should be greater than image orders and rect order
        self._handles.set_gl_state(depth_test=False)
        self._handles.interactive = True

        self.set_visible(False)

    def visible(self) -> bool:
        """Return whether the ROI is visible."""
        return bool(self._rect.visible)

    def set_visible(self, visible: bool) -> None:
        """Set the ROI as visible."""
        self._rect.visible = visible
        self._handles.visible = visible and self.selected()

    def selected(self) -> bool:
        """Return whether the ROI is selected."""
        return self._selected

    def set_selected(self, selected: bool) -> None:
        """Set the ROI as selected."""
        self._selected = selected
        self._handles.visible = selected and self.visible()

    def remove(self) -> None:
        """Remove the ROI from the scene."""
        self._rect.parent = None
        self._handles.parent = None

    def set_anchor(self, pos: tuple[float, float]) -> None:
        """Set the anchor of the ROI."""
        self._move_anchor = pos

    def bounding_box(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Return the bounding box of the ROI as top-left and bottom-right corners."""
        x1 = self._rect.center[0] - self._rect.width / 2
        y1 = self._rect.center[1] - self._rect.height / 2
        x2 = self._rect.center[0] + self._rect.width / 2
        y2 = self._rect.center[1] + self._rect.height / 2
        return (x1, y1), (x2, y2)

    def set_bounding_box(
        self, mi: tuple[float, float], ma: tuple[float, float]
    ) -> None:
        """Set the bounding box of the ROI using two diagonal points."""
        # NB: Support two diagonal points, not necessarily true min/max
        x1 = float(min(mi[0], ma[0]))
        y1 = float(min(mi[1], ma[1]))
        x2 = float(max(mi[0], ma[0]))
        y2 = float(max(mi[1], ma[1]))

        # Update rectangle
        self._rect.center = [(x1 + x2) / 2, (y1 + y2) / 2]
        self._rect.width = max(float(x2 - x1), 1e-30)
        self._rect.height = max(float(y2 - y1), 1e-30)

        # Update handles
        self._handle_data[0] = x1, y1
        self._handle_data[1] = x2, y1
        self._handle_data[2] = x2, y2
        self._handle_data[3] = x1, y2
        self._handles.set_data(pos=self._handle_data)

    # canvas.events.mouse_press.connect(self.on_mouse_press)
    def on_mouse_press(self, event: MouseEvent) -> None:
        """Handle the mouse press event."""
        canvas_pos = (event.pos[0], event.pos[1])
        world_pos = self._tform().map(canvas_pos)[:2]

        idx = self._under_mouse_index(world_pos)

        if idx is not None and idx >= 0:
            self.set_selected(True)
            opposite_idx = (idx + 2) % 4
            self._move_mode = ROIMoveMode.HANDLE
            self._move_anchor = tuple(self._handle_data[opposite_idx].copy())
        elif idx == -1:
            self.set_selected(True)
            self._move_mode = ROIMoveMode.TRANSLATE
            self._move_anchor = world_pos
        else:
            self.set_selected(False)
            self._move_mode = ROIMoveMode.NONE

    # canvas.events.mouse_move.connect(self.on_mouse_move)
    def on_mouse_move(self, event: MouseEvent) -> None:
        """Handle the mouse drag event."""
        # convert canvas -> world
        canvas_pos = (event.pos[0], event.pos[1])
        world_pos = self._tform().map(canvas_pos)[:2]
        # drawing a new roi
        if self._move_mode == ROIMoveMode.DRAW:
            self.set_bounding_box(self._move_anchor, world_pos)
        # moving a handle
        elif self._move_mode == ROIMoveMode.HANDLE:
            # The anchor is set to the opposite handle, which never moves.
            self.set_bounding_box(self._move_anchor, world_pos)
        # translating the whole roi
        elif self._move_mode == ROIMoveMode.TRANSLATE:
            # The anchor is the mouse position reported in the previous mouse event.
            dx = world_pos[0] - self._move_anchor[0]
            dy = world_pos[1] - self._move_anchor[1]
            # If the mouse moved (dx, dy) between events, the whole ROI needs to be
            # translated that amount.
            new_min = (self._handle_data[0, 0] + dx, self._handle_data[0, 1] + dy)
            new_max = (self._handle_data[2, 0] + dx, self._handle_data[2, 1] + dy)
            self._move_anchor = world_pos
            self.set_bounding_box(new_min, new_max)

    # canvas.events.mouse_release.connect(self.on_mouse_release)
    def on_mouse_release(self, event: MouseEvent) -> None:
        """Handle the mouse release event."""
        self._move_mode = ROIMoveMode.NONE

    def _tform(self) -> scene.transforms.BaseTransform:
        return self._rect.transforms.get_transform("canvas", "scene")

    def _under_mouse_index(self, pos: Sequence[float]) -> int | None:
        """Returns an int in [0, 3], -1, or None.

        If an int i, means that the handle at self._positions[i] is at pos.
        If -1, means that the mouse is within the rectangle.
        If None, there is no handle at pos.
        """
        rad2 = (self._handle_size / 2) ** 2
        for i, p in enumerate(self._handle_data):
            if (p[0] - pos[0]) ** 2 + (p[1] - pos[1]) ** 2 <= rad2:
                return i
        left, bottom = self._handle_data[0]
        right, top = self._handle_data[2]
        if left <= pos[0] <= right and bottom <= pos[1] <= top:
            return -1
        return None

    # def get_cursor(self, event: MouseEvent) -> QCursor | None:
    #     canvas_pos = (event.pos[0], event.pos[1])
    #     pos = self._tform().map(canvas_pos)[:2]
    #     if self._handle_under(pos) is not None:
    #         center = self._rect.center
    #         # if the mouse is in the top left or bottom right corner
    #         if pos[0] < center[0] and pos[1] < center[1]:
    #             cursor = QCursor(Qt.CursorShape.SizeFDiagCursor)
    #         # if the mouse is in the top right or bottom left corner
    #         if pos[0] > center[0] and pos[1] > center[1]:
    #             cursor = QCursor(Qt.CursorShape.SizeFDiagCursor)
    #         # if the mouse is in the top right or bottom left corner
    #         cursor = QCursor(Qt.CursorShape.SizeBDiagCursor)
    #     # if the mouse is in the center
    #     cursor = QCursor(Qt.CursorShape.SizeAllCursor)
    #     print(cursor)
    #     return cursor

    # canvas.events.mouse_move.connect(self.on_mouse_move)
    # def get_cursor(self, mme: MouseEvent) -> CursorType | None:
    #     """Return the cursor type."""
    #     canvas_pos = (mme.x, mme.y)
    #     pos = self._tform().map(canvas_pos)[:2]
    #     if self._handle_under(pos) is not None:
    #         center = self._rect.center
    #         if pos[0] < center[0] and pos[1] < center[1]:
    #             return CursorType.FDIAG_ARROW
    #         if pos[0] > center[0] and pos[1] > center[1]:
    #             return CursorType.FDIAG_ARROW
    #         return CursorType.BDIAG_ARROW
    #     return CursorType.ALL_ARROW
