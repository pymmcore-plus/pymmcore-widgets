from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

import numpy as np
from qtpy.QtCore import (
    QEvent,
    QItemSelection,
    QItemSelectionModel,
    QModelIndex,
    QObject,
    QPointF,
    Qt,
    Signal,
)
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QListView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from vispy.scene import SceneCanvas, ViewBox

from pymmcore_widgets.control._rois._vispy import RoiPolygon
from pymmcore_widgets.control._rois.canvas_event_filter import CanvasEventFilter
from pymmcore_widgets.control._rois.model import ROI, RectangleROI
from pymmcore_widgets.control._rois.q_roi_manager import QROIModel

if TYPE_CHECKING:
    from PyQt6.QtGui import QActionGroup
else:
    from qtpy.QtGui import QActionGroup


class SceneROIManager(QObject):
    """A class to link the ROI manager and the canvas."""

    modeChanged = Signal(str)

    def __init__(self, canvas: SceneCanvas) -> None:
        super().__init__()
        self._mode: Literal["select", "create-rect", "create-poly"] = "select"
        self._roi_visuals: dict[ROI, RoiPolygon] = {}

        self.roi_model = QROIModel()
        self.selection_model = QItemSelectionModel(self.roi_model)

        # prepare canvas and view
        self._canvas = canvas
        # create a viewbox if one doesn't exist
        for child in canvas.central_widget.children:
            if isinstance(child, ViewBox):
                self.view: ViewBox = child
                break
        else:
            self.view = canvas.central_widget.add_view(camera="panzoom")
        self._canvas_filter = CanvasEventFilter(self)
        canvas.native.installEventFilter(self._canvas_filter)

        # SIGNALS

        self.roi_model.rowsInserted.connect(self._on_rows_inserted)
        self.roi_model.rowsAboutToBeRemoved.connect(self._on_rows_about_to_be_removed)
        self.roi_model.dataChanged.connect(self._on_data_changed)
        self.selection_model.selectionChanged.connect(self._on_selection_changed)

    def clear_selection(self) -> None:
        """Clear the current selection."""
        self.selection_model.clearSelection()

    def select_roi(
        self,
        roi: ROI,
        command: QItemSelectionModel.SelectionFlag = QItemSelectionModel.SelectionFlag.ClearAndSelect,  # noqa: E501
    ) -> None:
        """Select a single ROI."""
        self.selection_model.select(self.roi_model.index_of(roi), command)

    def add_roi(self, roi: ROI | None = None) -> ROI:
        """Add a new ROI to the model."""
        return self.roi_model.addROI(roi)

    @property
    def mode(self) -> Literal["select", "create-rect", "create-poly"]:
        """Return the current mode of the ROI manager."""
        return self._mode

    @mode.setter
    def mode(self, mode: Literal["select", "create-rect", "create-poly"]) -> None:
        before, self._mode = self._mode, mode
        if before != mode:
            self.modeChanged.emit(mode)

    def canvas_to_world(self, point: QPointF) -> tuple[float, float]:
        """Convert a point from canvas coordinates to world coordinates."""
        return tuple(self.view.scene.transform.imap((point.x(), point.y()))[:2])

    def selected_rois(self) -> list[ROI]:
        """Return a list of selected ROIs."""
        return [
            index.internalPointer() for index in self.selection_model.selectedIndexes()
        ]

    def delete_selected_rois(self) -> None:
        """Delete the selected ROIs from the model."""
        for roi in self.selected_rois():
            self.roi_model.removeROI(roi)

    def _on_rows_about_to_be_removed(
        self, parent: QModelIndex, first: int, last: int
    ) -> None:
        # Remove the ROIs from the canvas
        for row in range(first, last + 1):
            roi = self.roi_model.index(row).internalPointer()
            self._remove_roi_from_canvas(roi)

    def _on_data_changed(
        self, top_left: QModelIndex, bottom_right: QModelIndex, roles: list[int]
    ) -> None:
        if set(roles) == {self.roi_model.VERTEX_ROLE}:
            do_update = self._update_roi_vertices
        else:
            do_update = self._update_roi_visual

        # Update the ROI on the canvas
        for row in range(top_left.row(), bottom_right.row() + 1):
            roi = self.roi_model.index(row).internalPointer()
            do_update(roi)

    def _on_selection_changed(
        self, selected: QItemSelection, deselected: QItemSelection
    ) -> None:
        for index in deselected.indexes():
            roi = cast("ROI", self.roi_model.index(index.row()).internalPointer())
            if visual := self._roi_visuals.get(roi):
                visual.set_selected(False)
        for index in selected.indexes():
            roi = cast("ROI", self.roi_model.index(index.row()).internalPointer())
            if visual := self._roi_visuals.get(roi):
                visual.set_selected(True)

    def _on_rows_inserted(self, parent: QModelIndex, first: int, last: int) -> None:
        for row in range(first, last + 1):
            roi = self.roi_model.index(row).internalPointer()
            self._add_roi_to_scene(roi)

    def _add_roi_to_scene(self, roi: ROI) -> None:
        # Create a polygon visual for the ROI
        self._roi_visuals[roi] = polygon = RoiPolygon(roi)
        polygon.parent = self.view.scene

    def _remove_roi_from_canvas(self, roi: ROI) -> None:
        # Remove the ROI from the canvas
        if visual := self._roi_visuals.pop(roi, None):
            visual.parent = None

    def _update_roi_visual(self, roi: ROI) -> None:
        # Update the the full ROI visual already on the canvas
        if visual := self._roi_visuals.get(roi):
            visual.update_from_roi(roi)

    def _update_roi_vertices(self, roi: ROI) -> None:
        # Update the only vertices of the ROI visual
        if visual := self._roi_visuals.get(roi):
            visual.update_vertices(roi.vertices)


class ROIScene(QWidget):
    def __init__(self, canvas: SceneCanvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ROI Manager")
        self.setGeometry(100, 100, 800, 600)

        self.roi_manager = SceneROIManager(canvas)
        self.roi_list = QListView()
        self.roi_list.setModel(self.roi_manager.roi_model)
        self.roi_list.setSelectionModel(self.roi_manager.selection_model)
        self.roi_list.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.roi_list.installEventFilter(self)

        toolbar = QToolBar()
        self._mode_actions = QActionGroup(self)
        # make three toggle-actions
        for title, shortcut, _mode in [
            ("Select", "v", "select"),
            ("Rectangle", "r", "create-rect"),
            ("Polygon", "p", "create-poly"),
        ]:
            if act := self._mode_actions.addAction(title):
                act.setShortcut(shortcut)
                act.setCheckable(True)
                act.setChecked(_mode == self.roi_manager.mode)
                act.triggered.connect(
                    lambda _, m=_mode: setattr(self.roi_manager, "mode", m)
                )
                toolbar.addAction(act)

        # LAYOUT

        layout = QHBoxLayout(self)
        left = QVBoxLayout()
        left.addWidget(toolbar)
        left.addWidget(canvas.native)
        layout.addLayout(left)
        layout.addWidget(self.roi_list)

        self.roi_manager.modeChanged.connect(self._on_mode_changed)

    def _on_mode_changed(
        self, mode: Literal["select", "create-rect", "create-poly"]
    ) -> None:
        # keep toolbar in sync
        action_names = {
            "select": "Select",
            "create-rect": "Rectangle",
            "create-poly": "Polygon",
        }
        for action in self._mode_actions.actions():
            action.setChecked(action.text() == action_names[mode])

    def eventFilter(self, source: QObject | None, event: QEvent | None) -> bool:
        """Filter events for the ROI list."""
        if not event:
            return False

        if isinstance(event, QKeyEvent):
            # when the delete key is pressed, remove the selected ROIs
            if (
                event.type() == QEvent.Type.KeyPress
                and not event.isAutoRepeat()
                and event.key() == Qt.Key.Key_Backspace
            ):
                self.roi_manager.delete_selected_rois()
                return True

        return False


if __name__ == "__main__":
    app = QApplication([])
    canvas = SceneCanvas()
    wdg = ROIScene(canvas)
    wdg.show()
    for i in range(4):
        if i % 2 == 0:
            x1, y1 = np.random.randint(0, 100, size=2)
            x2, y2 = np.random.randint(0, 100, size=2)
            roi: ROI = RectangleROI(
                top_left=(min(x1, x2), min(y1, y2)),
                bot_right=(max(x1, x2), max(y1, y2)),
            )
        else:
            npoints = np.random.randint(3, 7)
            roi = ROI(vertices=np.random.rand(npoints, 2) * 100)
        wdg.roi_manager.add_roi(roi).text = f"ROI {i + 1}"
    wdg.roi_manager.view.camera.set_range()

    app.exec()
