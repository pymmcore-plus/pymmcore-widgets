from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from qtpy.QtCore import QEvent, QObject, QPointF, Qt
from qtpy.QtGui import QCursor, QKeyEvent, QMouseEvent

from pymmcore_widgets.control._rois.roi_model import ROI, RectangleROI

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qtpy.QtWidgets import QWidget

    from pymmcore_widgets.control._rois.roi_manager import SceneROIManager


class CanvasEventFilter(QObject):
    """A QObject that filters events for a canvas."""

    def __init__(self, manager: SceneROIManager) -> None:
        super().__init__(manager._canvas.native)
        self._native: QWidget = manager._canvas.native
        self.manager = manager
        self.roi_model = manager.roi_model

        self._drag_roi: ROI | None = None
        self._drag_vertex_idx: int | None = None
        self._drag_start: tuple[float, float] = (0.0, 0.0)
        self._creating: ROI | None = None

        # how close (in canvas pixels) a click must be to a handle
        self._handle_pick_tol = 8

    def eventFilter(self, source: QObject | None, event: QEvent | None) -> bool:
        if isinstance(event, QKeyEvent):
            if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
                self._handle_key_press(event)
            # no key events ever get passed to vispy
            event.ignore()
            return True

        if isinstance(event, QMouseEvent):
            if event.type() == QEvent.Type.MouseButtonDblClick:
                self._handle_mouse_double_click(event)
            if event.type() == QEvent.Type.MouseButtonPress:
                return self._handle_mouse_press(event)
            if event.type() == QEvent.Type.MouseMove:
                if type(self._creating) is ROI:
                    self._handle_polygon_move(event)
                else:
                    return self._handle_mouse_move(event)
            if event.type() == QEvent.Type.MouseButtonRelease:
                return self._handle_mouse_release(event)

        return False

    def _handle_key_press(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Backspace:
            # delete selected ROIs
            self.manager.delete_selected_rois()

    def _handle_mouse_double_click(self, event: QMouseEvent) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            # finish creating the polygon
            if type(self._creating) is ROI:
                self._creating = None
                return True
        return False

    def _handle_mouse_press(self, event: QMouseEvent) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        sp = event.position()
        self._drag_start = wp = self.manager.canvas_to_world(sp)

        rois_at_wp = self.roi_model.pick_rois(wp)
        self._drag_vertex_idx = None
        self._drag_roi = None

        # 1) if alt is down and no ROIs at the clicked position
        #    then create a new rectangular ROI at the clicked position
        if self.manager.mode == "create-rect" and not rois_at_wp:
            # make a new rectangle ROI at the clicked position
            new_roi: ROI = RectangleROI(top_left=wp, bot_right=wp)
            self._creating = new_roi
            self._drag_vertex_idx = 2  # bottom-right corner
            self.roi_model.addROI(new_roi)
            self._start_dragging(new_roi)
            return True

        # 1) if ctrl is down and no ROIs at the clicked position
        #    then create a new polygon ROI at the clicked position
        if type(self._creating) is ROI:
            self._add_polygon_vertex(wp)
            return True
        elif self.manager.mode == "create-poly" and not rois_at_wp:
            self._creating = new_roi = ROI(vertices=np.array([wp]))
            self._add_polygon_vertex(wp)
            self.roi_model.addROI(new_roi)
            self._start_dragging(new_roi)
            return True

        # 2) if we've clicked on a vertex of an existing ROI
        #    then start a vertex-drag
        if (vertex := self._vertex_under_pointer(sp, rois_at_wp)) is not None:
            roi, idx = vertex
            self._drag_vertex_idx = idx
            self._start_dragging(roi)
            return True

        # 3) fallback to whole-ROI drag if we clicked on an ROI
        if hits := rois_at_wp:
            self._start_dragging(hits[0])
            return True

        # else let the canvas handle panning and other camera interactions
        self.manager.clear_selection()
        return False

    def _handle_polygon_move(self, event: QMouseEvent) -> bool:
        if type(self._creating) is not ROI:
            return False
        wp = self.manager.canvas_to_world(event.position())
        # drag the last point only
        self._creating.vertices[-1] = wp
        idx = self.roi_model.index_of(self._creating)
        self.roi_model.dataChanged.emit(idx, idx, [self.roi_model.VERTEX_ROLE])
        return True

    def _update_cursor(self, point: QPointF) -> None:
        # check for handle under pointer
        wp = self.manager.canvas_to_world(point)
        rois_at_wp = self.roi_model.pick_rois(wp)
        if self.manager.mode == "create-poly":
            self._native.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        elif self._vertex_under_pointer(point, rois_at_wp) is not None:
            self._native.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        elif rois_at_wp and self._drag_roi is None:
            self._native.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self._native.unsetCursor()

    def _handle_mouse_move(self, event: QMouseEvent) -> bool:
        btns = event.buttons()
        if btns == Qt.MouseButton.NoButton:
            # just hovering
            self._update_cursor(event.position())
            return False

        if btns & Qt.MouseButton.LeftButton and self._drag_roi:
            wp = self.manager.canvas_to_world(event.position())
            dx = wp[0] - self._drag_start[0]
            dy = wp[1] - self._drag_start[1]

            if self._drag_vertex_idx is not None:
                # move only the dragged vertex
                self._drag_roi.translate_vertex(self._drag_vertex_idx, dx, dy)
            else:
                # move the entire ROI
                self._drag_roi.translate(dx, dy)

            self._drag_start = wp
            idx = self.roi_model.index_of(self._drag_roi)
            self.roi_model.dataChanged.emit(idx, idx, [self.roi_model.VERTEX_ROLE])
            return True

        return False

    def _handle_mouse_release(self, event: QMouseEvent) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        if type(self._creating) is not ROI:
            self._creating = None
            self.manager.mode = "select"
            self._drag_roi = None
            self._drag_vertex_idx = None
            self._update_cursor(event.position())
        return False

    def _add_polygon_vertex(self, wp: tuple[float, float]) -> None:
        if type(self._creating) is not ROI:
            return
        self._creating.vertices = np.vstack([self._creating.vertices, wp])
        idx = self.roi_model.index_of(self._creating)
        self.roi_model.dataChanged.emit(idx, idx, [self.roi_model.VERTEX_ROLE])

    def _start_dragging(self, roi: ROI) -> None:
        self._drag_roi = roi
        if type(self._creating) is ROI:
            self._native.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        elif self._drag_vertex_idx is None:
            self._native.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        self.manager.select_roi(roi)

    def _vertex_under_pointer(
        self, point: QPointF, rois: Sequence[ROI] | None = None
    ) -> tuple[ROI, int] | None:
        """Return the index of the vertex under the pointer, or None."""
        for roi in rois or self.roi_model._rois:
            if (vertex_idx := self._find_vertex(point, roi)) is not None:
                return roi, vertex_idx
        return None

    def _find_vertex(self, sp: QPointF, roi: ROI) -> int | None:
        """Return index of roi vertex under screen-pos `sp`, or None."""
        # map the ROI vertices to screen coords
        # rather than converting the point to world... this avoids issues with zoom
        data = roi.vertices  # shape (N,2)
        pts = np.column_stack([data, np.zeros(len(data))])
        screen_vertices = self.manager.view.scene.transform.map(pts)[:, :2]

        # find the closest vertex to the screen position
        d2 = np.sum((screen_vertices - np.array([sp.x(), sp.y()])) ** 2, axis=1)
        idx = int(np.argmin(d2))
        if d2[idx] <= self._handle_pick_tol**2:
            return idx
        return None
