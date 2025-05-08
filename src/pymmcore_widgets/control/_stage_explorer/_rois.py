from __future__ import annotations

from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Any

import numpy as np
import vispy.color
from qtpy.QtCore import Qt
from qtpy.QtGui import QCursor
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
        left = float(min(corner1[0], corner2[0]))
        top = float(min(corner1[1], corner2[1]))
        right = float(max(corner1[0], corner2[0]))
        bot = float(max(corner1[1], corner2[1]))
        # update rectangle
        self._rect.center = [(left + right) / 2, (top + bot) / 2]
        self._rect.width = max(float(right - left), 1e-30)
        self._rect.height = max(float(bot - top), 1e-30)
        # update handles
        self._handle_data[0] = left, top
        self._handle_data[1] = right, top
        self._handle_data[2] = right, bot
        self._handle_data[3] = left, bot
        self._handles.set_data(pos=self._handle_data)

        self._text.pos = self._rect.center

    def get_cursor(self, event: MouseEvent) -> QCursor | None:
        """Return the cursor shape depending on the mouse position.

        If the mouse is over a handle, return a cursor indicating that the handle can be
        dragged. If the mouse is over the rectangle, return a cursor indicating that th
        whole ROI can be moved. Otherwise, return the default cursor.
        """
        if (grb := self.obj_at_pos(event.pos)) is None:
            # not grabbing anything return the default cursor
            return QCursor(Qt.CursorShape.ArrowCursor)

        # if the mouse is over a handle, return a cursor indicating that the handle
        # can be dragged
        if grb in (Grab.TOP_RIGHT, Grab.BOT_LEFT):
            return QCursor(Qt.CursorShape.SizeBDiagCursor)
        elif grb in (Grab.TOP_LEFT, Grab.BOT_RIGHT):
            return QCursor(Qt.CursorShape.SizeFDiagCursor)

        # if the mouse is over the rectangle, return a SizeAllCursor cursor
        # indicating that the whole ROI can be moved
        # grb == Grab.INSIDE
        return QCursor(Qt.CursorShape.SizeAllCursor)

    def connect(self, canvas: scene.SceneCanvas) -> None:
        """Connect the ROI events to the canvas."""
        canvas.events.mouse_move.connect(self.on_mouse_move)
        canvas.events.mouse_release.connect(self.on_mouse_release)

    def disconnect(self, canvas: scene.SceneCanvas) -> None:
        """Disconnect the ROI events from the canvas."""
        canvas.events.mouse_move.disconnect(self.on_mouse_move)
        canvas.events.mouse_release.disconnect(self.on_mouse_release)

    # ---------------------MOUSE EVENTS---------------------

    def anchor_at(self, grab: Grab, position: Sequence[float]) -> None:
        # if the mouse is over the rectangle, set the move mode to
        if grab == Grab.INSIDE:
            self._action_mode = ROIActionMode.MOVE
            self._move_anchor = self._tform().map(position)[:2]
        else:
            # if the mouse is over a handle, set the move mode to HANDLE
            self._action_mode = ROIActionMode.RESIZE
            self._move_anchor = tuple(self._handle_data[grab.opposite].copy())

    # for canvas.events.mouse_move.connect
    def on_mouse_move(self, event: MouseEvent) -> None:
        """Handle the mouse drag event."""
        # convert canvas -> world
        canvas_pos = (event.pos[0], event.pos[1])
        world_pos = self._tform().map(canvas_pos)[:2]
        # drawing a new roi
        if self._action_mode == ROIActionMode.CREATE:
            self.set_bounding_box(self._move_anchor, world_pos)
        # moving a handle
        elif self._action_mode == ROIActionMode.RESIZE:
            # The anchor is set to the opposite handle, which never moves.
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

    # for canvas.events.mouse_release.connect
    def on_mouse_release(self, event: MouseEvent) -> None:
        """Handle the mouse release event."""
        self._action_mode = ROIActionMode.NONE

    # ---------------------PRIVATE METHODS---------------------

    def _tform(self) -> scene.transforms.BaseTransform:
        return self._rect.transforms.get_transform("canvas", "scene")

    def obj_at_pos(self, epos: Sequence[float]) -> Grab | None:
        """Returns an int in [0, 3], -1, or None.

        If an int i, means that the handle at self._positions[i] is at pos.
        If -1, means that the mouse is within the rectangle.
        If None, there is no handle at pos.
        """
        # Get the transform from canvas to scene (world) coordinates
        transform = self._tform()
        # Convert mouse position from canvas to world coordinates
        world_pos = transform.map(epos)[:2]
        world_x, world_y = world_pos

        # FIXME
        # Get the pixel scale factor to adjust the handle hit detection based on zoom
        # level This converts a fixed screen size to the equivalent in world coordinates
        canvas_point1 = (epos[0], epos[1])
        canvas_point2 = (epos[0] + self._handle_size, epos[1])
        world_point1 = transform.map(canvas_point1)[:2]
        world_point2 = transform.map(canvas_point2)[:2]
        # distance in world units that corresponds to handle_size in canvas
        pixel_scale = np.sqrt(
            (world_point2[0] - world_point1[0]) ** 2
            + (world_point2[1] - world_point1[1]) ** 2
        )

        # Adjust handle hit radius based on zoom level
        handle_radius = pixel_scale / 2
        rad2 = handle_radius**2

        # Check if the mouse is over a handle
        for i, (handle_x, handle_y) in enumerate(self._handle_data):
            dist_to_handle = (handle_x - world_x) ** 2 + (handle_y - world_y) ** 2
            if dist_to_handle <= rad2:
                return Grab(i)

        # Check if the mouse is within the rectangle
        left, bottom = self._handle_data[0]
        right, top = self._handle_data[2]
        if left <= world_x <= right and bottom <= world_y <= top:
            return Grab.INSIDE
        return None


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
