from __future__ import annotations

import contextlib
import math
from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Any

import numpy as np
import useq
import vispy.color
from qtpy.QtCore import Qt
from qtpy.QtGui import QUndoCommand, QUndoStack
from vispy import scene
from vispy.app.canvas import MouseEvent
from vispy.scene import Compound

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qtpy.QtGui import QUndoStack
    from vispy.app.canvas import MouseEvent

    from ._stage_viewer import StageViewer


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


class _RoiCommand(QUndoCommand):
    def __init__(self, manager: ROIManager, roi: ROIRectangle) -> None:
        super().__init__("Add ROI")
        self._manager = manager
        self._roi = roi


class InsertRoiCommand(_RoiCommand):
    def undo(self) -> None:
        self._manager._remove_roi(self._roi)

    def redo(self) -> None:
        self._manager._add_roi(self._roi)


class DeleteRoiCommand(_RoiCommand):
    def undo(self) -> None:
        self._manager._add_roi(self._roi)

    def redo(self) -> None:
        self._manager._remove_roi(self._roi)


class ROIManager:
    """Manager for ROI rectangles in the StageViewer.

    This class is responsible for creating, adding, removing, and updating ROIs.
    It also handles mouse events related to ROIs and maintains an undo stack
    for ROI operations.

    Parameters
    ----------
    stage_viewer : StageViewer
        The stage viewer where ROIs will be displayed.
    undo_stack : QUndoStack
        The undo stack for ROI operations.
    """

    def __init__(self, stage_viewer: StageViewer, undo_stack: QUndoStack):
        self._stage_viewer = stage_viewer
        self._undo_stack = undo_stack
        self._rois: set[ROIRectangle] = set()

    @property
    def rois(self) -> set[ROIRectangle]:
        """List of ROIs in the scene."""
        return self._rois

    def value(
        self, fov_w: float, fov_h: float, z_pos: float
    ) -> list[useq.AbsolutePosition]:
        """Return a list of `GridFromEdges` objects from the drawn rectangles."""
        # TODO: add a way to set overlap
        positions = []
        for rect in self._rois:
            grid_plan = self._build_grid_plan(rect, fov_w, fov_h, z_pos)
            if isinstance(grid_plan, useq.AbsolutePosition):
                positions.append(grid_plan)
            else:
                x, y = rect.center
                pos = useq.AbsolutePosition(
                    x=x,
                    y=y,
                    z=z_pos,
                    sequence=useq.MDASequence(grid_plan=grid_plan),
                )
                positions.append(pos)
        return positions

    def remove_all_rois(self) -> None:
        """Delete all the ROIs."""
        while self._rois:
            roi = self._rois.pop()
            self._remove_roi(roi)

    def _active_roi(self) -> ROIRectangle | None:
        """Return the active ROI (the one that is currently selected)."""
        return next((roi for roi in self._rois if roi.selected()), None)

    def remove_selected_roi(self) -> None:
        """Delete the selected ROI from the scene."""
        if (roi := self._active_roi()) is not None:
            self._undo_stack.push(DeleteRoiCommand(self, roi))

    def create_roi(self, canvas_pos: tuple[float, float]) -> ROIRectangle:
        """Create a new ROI rectangle and connect its events."""
        roi = ROIRectangle(self._stage_viewer.view.scene)
        roi.visible = True
        roi.set_selected(True)
        roi.set_anchor(roi._canvas_to_world(canvas_pos))
        return roi

    def _add_roi(self, roi: ROIRectangle) -> None:
        """Add a ROI to the scene."""
        roi.parent = self._stage_viewer.view.scene
        roi.connect(self._stage_viewer.canvas)
        self._rois.add(roi)

    def _remove_roi(self, roi: ROIRectangle) -> None:
        """Remove a ROI from the scene."""
        if roi in self._rois:
            roi.parent = None
            self._rois.remove(roi)
            with contextlib.suppress(Exception):
                roi.disconnect(self._stage_viewer.canvas)

    def handle_mouse_press(self, event: MouseEvent) -> bool:
        """Handle mouse press event for ROIs.

        Returns
        -------
        bool
            True if the event was handled, False otherwise.
        """
        (event.pos[0], event.pos[1])

        picked = None
        for roi in self._rois:
            if not picked and (grb := roi.obj_at_pos(event.pos)) is not None:
                roi.anchor_at(grb, event.pos)
                roi.set_selected(True)
                picked = roi
            else:
                roi.set_selected(False)

        if self._active_roi() is not None:
            self._stage_viewer.view.camera.interactive = False
            return True

        return False

    def create_roi_at(self, event: MouseEvent, create_roi_mode: bool) -> bool:
        """Create a new ROI at the given position if in create ROI mode.

        Returns
        -------
        bool
            True if a ROI was created, False otherwise.
        """
        # (button = 1 is left mouse button)
        if create_roi_mode and event.button == 1:
            self._stage_viewer.view.camera.interactive = False
            # create the ROI rectangle for the first time
            canvas_pos = (event.pos[0], event.pos[1])
            roi = self.create_roi(canvas_pos)
            self._undo_stack.push(InsertRoiCommand(self, roi))
            return True
        return False

    def handle_mouse_move(self, event: MouseEvent) -> None:
        """Update the roi text when the roi changes size."""
        if (roi := self._active_roi()) is None:
            # reset cursor to default
            self._stage_viewer.canvas.native.setCursor(Qt.CursorShape.ArrowCursor)
            return

        # set cursor
        cursor = roi.get_cursor(event)
        self._stage_viewer.canvas.native.setCursor(cursor)

        # update roi text
        px = self._mmc.getPixelSizeUm()
        fov_w = self._mmc.getImageWidth() * px
        fov_h = self._mmc.getImageHeight() * px
        z_pos = self._mmc.getFocusPosition()
        grid_plan = self._build_grid_plan(roi, fov_w, fov_h, z_pos)
        try:
            pos = list(grid_plan)
            rows = max(r.row for r in pos if r.row is not None) + 1
            cols = max(c.col for c in pos if c.col is not None) + 1
            roi.set_text(f"r{rows} x c{cols}")
        except AttributeError:
            breakpoint()
            roi.set_text("r1 x c1")

    def _build_grid_plan(
        self, roi: ROIRectangle, fov_w: float, fov_h: float, z_pos: float
    ) -> useq.GridFromEdges | useq.AbsolutePosition:
        """Return a `GridFromEdges` plan from the roi and fov width and height."""
        top_left, bottom_right = roi.bounding_box()

        # if the width and the height of the roi are smaller than the fov width and
        # height, return a single position at the center of the roi and not a grid plan.
        w = bottom_right[0] - top_left[0]
        h = bottom_right[1] - top_left[1]
        if w < fov_w and h < fov_h:
            return useq.AbsolutePosition(
                x=top_left[0] + (w / 2),
                y=top_left[1] + (h / 2),
                z=z_pos,
            )
        # NOTE: we need to add the fov_w/2 and fov_h/2 to the top_left and
        # bottom_right corners respectively because the grid plan is created
        # considering the center of the fov and we want the roi to define the edges
        # of the grid plan.
        return useq.GridFromEdges(
            top=top_left[1] - (fov_h / 2),
            bottom=bottom_right[1] + (fov_h / 2),
            left=top_left[0] + (fov_w / 2),
            right=bottom_right[0] - (fov_w / 2),
            fov_width=fov_w,
            fov_height=fov_h,
        )
