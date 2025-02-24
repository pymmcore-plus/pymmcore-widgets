from collections.abc import Sequence
from enum import Enum
from typing import Any

import numpy as np
import vispy.color
from qtpy.QtCore import Qt
from qtpy.QtGui import QCursor
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
        # flag to indicate if the ROI is selected
        self._selected = False
        # flag to indicate the move mode
        self._move_mode: ROIMoveMode = ROIMoveMode.DRAW
        # anchor point for the move mode
        self._move_anchor: tuple[float, float] = (0, 0)

        self._rect = scene.Rectangle(
            center=[0, 0],
            width=1,
            height=1,
            color=None,
            border_color=vispy.color.Color("yellow"),
            border_width=2,
            parent=parent,
        )
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
        self._handles.set_gl_state(depth_test=False)
        self._handles.interactive = True

        # Add text at the center of the rectangle
        self._text = scene.Text(
            text="",
            bold=True,
            color="yellow",
            font_size=12,
            anchor_x="center",
            anchor_y="center",
            depth_test=False,
            parent=parent,
        )

        self.set_visible(False)

    @property
    def center(self) -> tuple[float, float]:
        """Return the center of the ROI."""
        return tuple(self._rect.center)

    # ---------------------PUBLIC METHODS---------------------

    def visible(self) -> bool:
        """Return whether the ROI is visible."""
        return bool(self._rect.visible)

    def set_visible(self, visible: bool) -> None:
        """Set the ROI as visible."""
        self._rect.visible = visible
        self._handles.visible = visible and self.selected()
        self._text.visible = visible

    def selected(self) -> bool:
        """Return whether the ROI is selected."""
        return self._selected

    def set_selected(self, selected: bool) -> None:
        """Set the ROI as selected."""
        self._selected = selected
        self._handles.visible = selected and self.visible()
        self._text.visible = selected

    def remove(self) -> None:
        """Remove the ROI from the scene."""
        self._rect.parent = None
        self._handles.parent = None
        self._text.parent = None

    def set_anchor(self, pos: tuple[float, float]) -> None:
        """Set the anchor of the ROI.

        The anchor is the point where the ROI is created or moved from.
        """
        self._move_anchor = pos

    def set_text(self, text: str) -> None:
        """Set the text of the ROI."""
        self._text.text = text

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
        x1 = float(min(mi[0], ma[0]))
        y1 = float(min(mi[1], ma[1]))
        x2 = float(max(mi[0], ma[0]))
        y2 = float(max(mi[1], ma[1]))
        # update rectangle
        self._rect.center = [(x1 + x2) / 2, (y1 + y2) / 2]
        self._rect.width = max(float(x2 - x1), 1e-30)
        self._rect.height = max(float(y2 - y1), 1e-30)
        # update handles
        self._handle_data[0] = x1, y1
        self._handle_data[1] = x2, y1
        self._handle_data[2] = x2, y2
        self._handle_data[3] = x1, y2
        self._handles.set_data(pos=self._handle_data)

        self._text.pos = self._rect.center

    def get_cursor(self, event: MouseEvent) -> QCursor | None:
        """Return the cursor shape depending on the mouse position.

        If the mouse is over a handle, return a cursor indicating that the handle can be
        dragged. If the mouse is over the rectangle, return a cursor indicating that th
        whole ROI can be moved. Otherwise, return the default cursor.
        """
        canvas_pos = (event.pos[0], event.pos[1])
        pos = self._tform().map(canvas_pos)[:2]
        if (idx := self._under_mouse_index(pos)) is not None:
            # if the mouse is over the rectangle, return a SizeAllCursor cursor
            # indicating that the whole ROI can be moved
            if idx == -1:
                return QCursor(Qt.CursorShape.SizeAllCursor)
            # if the mouse is over a handle, return a cursor indicating that the handle
            # can be dragged
            elif idx >= 0:
                return QCursor(Qt.CursorShape.DragMoveCursor)
            # otherwise, return the default cursor
            else:
                return QCursor(Qt.CursorShape.ArrowCursor)
        return QCursor(Qt.CursorShape.ArrowCursor)

    def connect(self, canvas: scene.SceneCanvas) -> None:
        """Connect the ROI events to the canvas."""
        canvas.events.mouse_press.connect(self.on_mouse_press)
        canvas.events.mouse_move.connect(self.on_mouse_move)
        canvas.events.mouse_release.connect(self.on_mouse_release)

    def disconnect(self, canvas: scene.SceneCanvas) -> None:
        """Disconnect the ROI events from the canvas."""
        canvas.events.mouse_press.disconnect(self.on_mouse_press)
        canvas.events.mouse_move.disconnect(self.on_mouse_move)
        canvas.events.mouse_release.disconnect(self.on_mouse_release)

    # ---------------------MOUSE EVENTS---------------------

    # for canvas.events.mouse_press.connect
    def on_mouse_press(self, event: MouseEvent) -> None:
        """Handle the mouse press event."""
        canvas_pos = (event.pos[0], event.pos[1])
        world_pos = self._tform().map(canvas_pos)[:2]

        # check if the mouse is over a handle or the rectangle
        idx = self._under_mouse_index(world_pos)

        # if the mouse is over a handle, set the move mode to HANDLE
        if idx is not None and idx >= 0:
            self.set_selected(True)
            opposite_idx = (idx + 2) % 4
            self._move_mode = ROIMoveMode.HANDLE
            self._move_anchor = tuple(self._handle_data[opposite_idx].copy())
        # if the mouse is over the rectangle, set the move mode to
        elif idx == -1:
            self.set_selected(True)
            self._move_mode = ROIMoveMode.TRANSLATE
            self._move_anchor = world_pos
        # if the mouse is not over a handle or the rectangle, set the move mode to
        else:
            self.set_selected(False)
            self._move_mode = ROIMoveMode.NONE

    # for canvas.events.mouse_move.connect
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

    # for canvas.events.mouse_release.connect
    def on_mouse_release(self, event: MouseEvent) -> None:
        """Handle the mouse release event."""
        self._move_mode = ROIMoveMode.NONE

    # ---------------------PRIVATE METHODS---------------------

    def _tform(self) -> scene.transforms.BaseTransform:
        return self._rect.transforms.get_transform("canvas", "scene")

    def _under_mouse_index(self, pos: Sequence[float]) -> int | None:
        """Returns an int in [0, 3], -1, or None.

        If an int i, means that the handle at self._positions[i] is at pos.
        If -1, means that the mouse is within the rectangle.
        If None, there is no handle at pos.
        """
        # check if the mouse is over a handle
        rad2 = (self._handle_size / 2) ** 2
        for i, p in enumerate(self._handle_data):
            if (p[0] - pos[0]) ** 2 + (p[1] - pos[1]) ** 2 <= rad2:
                return i
        # check if the mouse is within the rectangle
        left, bottom = self._handle_data[0]
        right, top = self._handle_data[2]
        return -1 if left <= pos[0] <= right and bottom <= pos[1] <= top else None
