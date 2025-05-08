from __future__ import annotations

import math
from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Any

import numpy as np
import vispy.color
from qtpy.QtCore import Qt
from vispy import scene
from vispy.scene import Compound

if TYPE_CHECKING:
    from collections.abc import Sequence

    from vispy.app.canvas import MouseEvent


class ROIActionMode(Enum):
    """ROI modes."""

    NONE = "none"
    CREATE = "create"
    RESIZE = "resize"
    MOVE = "move"


class Grab(IntEnum):
    """Enum for grabbable objects."""

    INSIDE = -1
    BOT_LEFT = 0
    BOT_RIGHT = 1
    TOP_RIGHT = 2
    TOP_LEFT = 3

    @property
    def opposite(self) -> Grab:
        """Return the opposite handle."""
        return Grab((self + 2) % 4)


_CURSOR_MAP: dict[Grab | None, Qt.CursorShape] = {
    None: Qt.CursorShape.ArrowCursor,
    Grab.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
    Grab.BOT_LEFT: Qt.CursorShape.SizeBDiagCursor,
    Grab.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
    Grab.BOT_RIGHT: Qt.CursorShape.SizeFDiagCursor,
    Grab.INSIDE: Qt.CursorShape.SizeAllCursor,
}


class ROIRectangle(Compound):
    """A rectangle ROI."""

    def __init__(self, parent: Any) -> None:
        # flag to indicate if the ROI is selected
        self._selected = False
        self._action_mode: ROIActionMode = ROIActionMode.CREATE
        # anchor point for the move mode, this is the "non-moving" point
        # when moving or resizing the ROI
        self._move_anchor: tuple[float, float] = (0, 0)

        self._rect = scene.Rectangle(
            center=[0, 0],
            width=1,
            height=1,
            color=vispy.color.Color("transparent"),
            border_color=vispy.color.Color("yellow"),
            border_width=2,
        )

        # BL, BR, TR, TL
        self._handle_data = np.zeros((4, 2))
        self._handle_size = 20  # px
        self._handles = scene.Markers(
            pos=self._handle_data,
            size=self._handle_size,
            scaling=False,  # "fixed"
            face_color=vispy.color.Color("white"),
        )

        # Add text at the center of the rectangle
        self._text = scene.Text(
            text="",
            bold=True,
            color="yellow",
            font_size=12,
            anchor_x="center",
            anchor_y="center",
            depth_test=False,
        )

        super().__init__([self._rect, self._handles, self._text])
        self.parent = parent
        self.set_gl_state(depth_test=False)

    @property
    def center(self) -> tuple[float, float]:
        """Return the center of the ROI."""
        return tuple(self._rect.center)

    # ---------------------PUBLIC METHODS---------------------

    def selected(self) -> bool:
        """Return whether the ROI is selected."""
        return self._selected

    def set_selected(self, selected: bool) -> None:
        """Set the ROI as selected."""
        self._selected = selected
        self._handles.visible = selected and self.visible
        self._text.visible = selected

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
        y1 = self._rect.center[1] + self._rect.height / 2
        x2 = self._rect.center[0] + self._rect.width / 2
        y2 = self._rect.center[1] - self._rect.height / 2
        return (x1, y1), (x2, y2)

    def set_bounding_box(
        self, corner1: tuple[float, float], corner2: tuple[float, float]
    ) -> None:
        """Set the bounding box of the ROI using two diagonal points."""
        # Unpack and sort coordinates
        left, right = sorted((corner1[0], corner2[0]))
        bot, top = sorted((corner1[1], corner2[1]))

        # Compute center, width, height
        center_x = (left + right) / 2.0
        center_y = (bot + top) / 2.0
        width = max(right - left, 1e-30)
        height = max(top - bot, 1e-30)

        # Update rectangle visual
        self._rect.center = (center_x, center_y)
        self._rect.width = width
        self._rect.height = height

        self._handle_data[:] = [(left, bot), (right, bot), (right, top), (left, top)]
        self._handles.set_data(pos=self._handle_data)

        # Keep text centered
        self._text.pos = self._rect.center

    def get_cursor(self, event: MouseEvent) -> Qt.CursorShape:
        """Return the cursor shape depending on the mouse position.

        If the mouse is over a handle, return a cursor indicating that the handle can be
        dragged. If the mouse is over the rectangle, return a cursor indicating that th
        whole ROI can be moved. Otherwise, return the default cursor.
        """
        grab = self.obj_at_pos(event.pos)
        return _CURSOR_MAP.get(grab, Qt.CursorShape.ArrowCursor)

    def connect(self, canvas: scene.SceneCanvas) -> None:
        """Connect the ROI events to the canvas."""
        canvas.events.mouse_move.connect(self.on_mouse_move)
        canvas.events.mouse_release.connect(self.on_mouse_release)

    def disconnect(self, canvas: scene.SceneCanvas) -> None:
        """Disconnect the ROI events from the canvas."""
        canvas.events.mouse_move.disconnect(self.on_mouse_move)
        canvas.events.mouse_release.disconnect(self.on_mouse_release)

    def obj_at_pos(self, canvas_position: Sequence[float]) -> Grab | None:
        """Return the object at the given position."""
        # 1) Convert to world coords
        world_x, world_y = self._canvas_to_world(canvas_position)

        # 2) Compute world-space length of one handle_size in canvas
        shifted = (canvas_position[0] + self._handle_size, canvas_position[1])
        shift_x, shift_y = self._canvas_to_world(shifted)
        pix_scale = math.hypot(shift_x - world_x, shift_y - world_y)
        handle_radius2 = (pix_scale / 2) ** 2

        # 3) hit-test against all handles
        for i, (hx, hy) in enumerate(self._handle_data):
            dx, dy = hx - world_x, hy - world_y
            if dx * dx + dy * dy <= handle_radius2:
                return Grab(i)

        # 4) Check “inside” the rectangle
        (left, bottom), _, (right, top), _ = self._handle_data
        if left <= world_x <= right and bottom <= world_y <= top:
            return Grab.INSIDE

        return None

    # ---------------------MOUSE EVENTS---------------------

    def anchor_at(self, grab: Grab, position: Sequence[float]) -> None:
        # if the mouse is over the rectangle, set the move mode to
        if grab == Grab.INSIDE:
            self._action_mode = ROIActionMode.MOVE
            self._move_anchor = self._canvas_to_world(position)
        else:
            # if the mouse is over a handle, set the move mode to HANDLE
            self._action_mode = ROIActionMode.RESIZE
            self._move_anchor = tuple(self._handle_data[grab.opposite].copy())

    def on_mouse_move(self, event: MouseEvent) -> None:
        """Handle the mouse drag event."""
        # convert canvas -> world
        world_pos = self._canvas_to_world(event.pos)
        # drawing or resizing the ROI
        if self._action_mode in {ROIActionMode.CREATE, ROIActionMode.RESIZE}:
            self.set_bounding_box(self._move_anchor, world_pos)
        # translating the whole roi
        elif self._action_mode == ROIActionMode.MOVE:
            # The anchor is the mouse position reported in the previous mouse event.
            dx = world_pos[0] - self._move_anchor[0]
            dy = world_pos[1] - self._move_anchor[1]
            # If the mouse moved (dx, dy) between events, the whole ROI needs to be
            # translated that amount.
            new_min = (self._handle_data[0, 0] + dx, self._handle_data[0, 1] + dy)
            new_max = (self._handle_data[2, 0] + dx, self._handle_data[2, 1] + dy)
            self._move_anchor = world_pos
            self.set_bounding_box(new_min, new_max)

    def on_mouse_release(self, event: MouseEvent) -> None:
        """Handle the mouse release event."""
        self._action_mode = ROIActionMode.NONE

    # ---------------------PRIVATE METHODS---------------------

    def _canvas_to_world(self, position: Sequence[float]) -> tuple[float, float]:
        tform = self._rect.transforms.get_transform("canvas", "scene")
        cx, cy = tform.map(position)[:2]
        return float(cx), float(cy)
        return self._rect.transforms.get_transform("canvas", "scene")
