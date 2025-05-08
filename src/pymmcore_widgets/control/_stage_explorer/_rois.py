from __future__ import annotations

import contextlib
import math
from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Any, cast

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

    def qt_cursor(self) -> Qt.CursorShape:
        """Return the Qt cursor for this handle."""
        _CURSOR_MAP.get(self, Qt.CursorShape.ArrowCursor)


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

    def connect(self, canvas: scene.SceneCanvas) -> None:
        """Connect the ROI events to the canvas."""
        canvas.events.mouse_move.connect(self.on_mouse_move)

    def disconnect(self, canvas: scene.SceneCanvas) -> None:
        """Disconnect the ROI events from the canvas."""
        canvas.events.mouse_move.disconnect(self.on_mouse_move)

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

    def create_useq_position(
        self, fov_w: float, fov_h: float, z_pos: float
    ) -> useq.AbsolutePosition:
        """Return a useq.AbsolutePosition object that covers the ROI."""
        (left, top), (right, bottom) = self.bounding_box()
        pos = useq.AbsolutePosition(x=self.center[0], y=self.center[1], z=z_pos)

        # if the width and the height of the roi are smaller than the fov width and
        # a single position at the center of the roi is sufficient, otherwise create a
        # grid plan that covers the roi
        if abs(right - left) > fov_w or abs(bottom - top) > fov_h:
            # NOTE: we need to add the fov_w/2 and fov_h/2 to the top_left and
            # bottom_right corners respectively because the grid plan is created
            # considering the center of the fov and we want the roi to define the edges
            # of the grid plan.
            pos.sequence = useq.MDASequence(
                grid_plan=useq.GridFromEdges(
                    top=top,
                    bottom=bottom,
                    left=left,
                    right=right,
                    fov_width=fov_w,
                    fov_height=fov_h,
                )
            )
        return pos

    def update_rows_cols_text(self, fov_w: float, fov_h: float, z_pos: float) -> None:
        """Update the text of the ROI with the number of rows and columns."""
        pos = self.create_useq_position(fov_w, fov_h, z_pos)
        if pos.sequence:
            grid = cast("useq.GridFromEdges", pos.sequence.grid_plan)
            nc = math.ceil(abs(grid.right - grid.left) / fov_w)
            nr = math.ceil(abs(grid.top - grid.bottom) / fov_h)
            self.set_text(f"r{nr} x c{nc}")
        else:
            self.set_text("r1 x c1")

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
        self._manager._remove(self._roi)

    def redo(self) -> None:
        self._manager._add(self._roi)


class DeleteRoiCommand(_RoiCommand):
    def undo(self) -> None:
        self._manager._add(self._roi)

    def redo(self) -> None:
        self._manager._remove(self._roi)


class ClearRoisCommand(QUndoCommand):
    def __init__(self, manager: ROIManager) -> None:
        super().__init__("Clear ROIs")
        self._manager = manager
        self._rois = set(self._manager.rois)

    def undo(self) -> None:
        for roi in self._rois:
            self._manager._add(roi)

    def redo(self) -> None:
        for roi in self._rois:
            self._manager._remove(roi)


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

    # undo/redoable operations ---------------------------

    def selected_roi(self) -> ROIRectangle | None:
        """Return the active ROI (the one that is currently selected)."""
        return next((roi for roi in self._rois if roi.selected()), None)

    def clear(self) -> None:
        """Delete all the ROIs."""
        self._undo_stack.push(ClearRoisCommand(self))

    def reset_action_modes(self) -> None:
        for roi in self._rois:
            roi._action_mode = ROIActionMode.NONE

    def remove_selected_roi(self) -> None:
        """Delete the selected ROI from the scene."""
        if (roi := self.selected_roi()) is not None:
            self._undo_stack.push(DeleteRoiCommand(self, roi))

    def create_roi_at(self, position: Sequence[float]) -> None:
        """Create a new ROI at the given position."""
        roi = ROIRectangle(self._stage_viewer.view.scene)
        roi.visible = True
        roi.set_selected(True)
        roi.set_anchor(roi._canvas_to_world(position))
        self._undo_stack.push(InsertRoiCommand(self, roi))

    # direct manipulation of ROIs (NOT undoable) ---------------------------

    def _add(self, roi: ROIRectangle) -> None:
        """Add a ROI to the scene."""
        if roi in self._rois:
            return
        roi.parent = self._stage_viewer.view.scene
        roi.connect(self._stage_viewer.canvas)
        self._rois.add(roi)

    def _remove(self, roi: ROIRectangle) -> None:
        """Remove a ROI from the scene."""
        if roi in self._rois:
            roi.parent = None
            self._rois.remove(roi)
            with contextlib.suppress(Exception):
                roi.disconnect(self._stage_viewer.canvas)

    def select_roi_at(self, position: Sequence[float]) -> ROIRectangle | None:
        picked = None
        for roi in self._rois:
            if not picked and (grb := roi.obj_at_pos(position)) is not None:
                roi.anchor_at(grb, position)
                roi.set_selected(True)
                picked = roi
            else:
                roi.set_selected(False)
        return picked

    def value(
        self, fov_w: float, fov_h: float, z_pos: float
    ) -> list[useq.AbsolutePosition]:
        """Return a list of useq.Position objects from the drawn rectangles."""
        # TODO: add a way to set overlap
        return [roi.create_useq_position(fov_w, fov_h, z_pos) for roi in self._rois]
