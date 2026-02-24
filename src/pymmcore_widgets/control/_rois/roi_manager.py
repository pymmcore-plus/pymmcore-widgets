from __future__ import annotations

from typing import TYPE_CHECKING, Literal

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
    QHBoxLayout,
    QListView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from superqt import QIconifyIcon
from vispy.scene import SceneCanvas, ViewBox

from ._vispy import RoiPolygon
from .canvas_event_filter import CanvasROIEventFilter
from .q_roi_model import QROIModel

if TYPE_CHECKING:
    from PyQt6.QtGui import QActionGroup

    from .roi_model import ROI
else:
    from qtpy.QtGui import QActionGroup

GRAY = "#666"


class SceneROIManager(QObject):
    """A manager for ROIs in a SceneCanvas.

    This object handles the creation, selection, and management of ROIs in a
    SceneCanvas. It provides methods to add, remove, and update ROIs, as well as to
    change the current mode of interaction (selecting, creating rectangles, or creating
    polygons).

    It combines a `QROIModel` with a `QItemSelectionModel` to manage the ROIs and their
    selection state.  It also installs a `CanvasROIEventFilter` on the provided
    vispy `SceneCanvas` to handle mouse and keyboard events related to ROIS.  Note, that
    the event filter stops ALL key events from being passed to the vispy canvas.

    (Because QROIModel is a QAbstractListModel, it could also be used in parallel with
    a `QListView`, to display the ROIs in a tabular format).
    """

    modeChanged = Signal(str)

    def __init__(self, canvas: SceneCanvas) -> None:
        super().__init__()
        self._mode: Literal["select", "create-rect", "create-poly"] = "select"
        self._roi_visuals: dict[ROI, RoiPolygon] = {}

        self._fov_size: tuple[float, float] | None = None

        self.roi_model = QROIModel()
        self.selection_model = QItemSelectionModel(self.roi_model)
        self.mode_actions = QActionGroup(self)
        # make three toggle-actions
        for title, shortcut, _mode, icon in [
            ("Select", "v", "select", "mdi:cursor-default-outline"),
            ("Rectangle", "r", "create-rect", "mdi:vector-square"),
            ("Polygon", "p", "create-poly", "mdi:vector-polygon"),
        ]:
            if act := self.mode_actions.addAction(title):
                act.setCheckable(True)
                act.setChecked(_mode == self._mode)
                act.setShortcut(shortcut)
                act.setToolTip(f"{title} ({shortcut.upper()})")
                act.setData(_mode)
                act.setIcon(QIconifyIcon(icon, color=GRAY))
                act.triggered.connect(lambda _, m=_mode: setattr(self, "mode", m))

        # prepare canvas and view
        self._canvas = canvas
        # create a viewbox if one doesn't exist
        for child in canvas.central_widget.children:
            if isinstance(child, ViewBox):
                self.view: ViewBox = child
                break
        else:
            self.view = canvas.central_widget.add_view(camera="panzoom")

        self._canvas_filter = CanvasROIEventFilter(self)
        canvas.native.installEventFilter(self._canvas_filter)

        # SIGNALS

        self.roi_model.rowsInserted.connect(self._on_rows_inserted)
        self.roi_model.rowsAboutToBeRemoved.connect(self._on_rows_about_to_be_removed)
        self.roi_model.dataChanged.connect(self._on_data_changed)
        self.selection_model.selectionChanged.connect(self._on_selection_changed)

    # PUBLIC API ------------------------------------------------------------

    def clear_selection(self) -> None:
        """Clear the current selection (unselect all)."""
        self.selection_model.clearSelection()

    def select_roi(self, roi: ROI) -> None:
        """Select a single ROI, (unselect all others)."""
        self.selection_model.select(
            self.roi_model.index_of(roi),
            QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )

    def add_roi(self, roi: ROI | None = None) -> ROI:
        """Add a new ROI to the model."""
        return self.roi_model.addROI(roi)

    def update_fovs(self, fov: tuple[float, float]) -> None:
        """Update the FOVs of all ROIs."""
        self._fov_size = fov
        for row in range(self.roi_model.rowCount()):
            roi = self.roi_model.getRoi(row)
            roi.fov_size = fov
            self.roi_model.emitDataChange(roi)

    @property
    def mode(self) -> Literal["select", "create-rect", "create-poly"]:
        """Return the current mode of the ROI manager."""
        return self._mode

    @mode.setter
    def mode(self, mode: Literal["select", "create-rect", "create-poly"]) -> None:
        if mode not in {"select", "create-rect", "create-poly"}:
            raise ValueError(f"Invalid mode: {mode}")
        before, self._mode = self._mode, mode
        # update the action group
        for action in self.mode_actions.actions():
            action.setChecked(action.data() == mode)
        if before != mode:
            self.modeChanged.emit(mode)

    def canvas_to_world(self, point: QPointF) -> tuple[float, float]:
        """Convert a point from canvas coordinates to world coordinates."""
        return tuple(self.view.scene.transform.imap((point.x(), point.y()))[:2])

    def selected_rois(self) -> list[ROI]:
        """Return a list of selected ROIs."""
        return [
            index.data(QROIModel.ROI_ROLE)
            for index in self.selection_model.selectedIndexes()
        ]

    def all_rois(self) -> list[ROI]:
        """Return a list of all ROIs."""
        return [self.roi_model.getRoi(row) for row in range(self.roi_model.rowCount())]

    def delete_selected_rois(self) -> None:
        """Delete the selected ROIs from the model."""
        for roi in self.selected_rois():
            self.roi_model.removeROI(roi)

    def clear(self) -> None:
        """Clear all ROIs from the model."""
        self.roi_model.clear()

    # PRIVATE -----------------------------------------------------------

    def _on_rows_about_to_be_removed(
        self, parent: QModelIndex, first: int, last: int
    ) -> None:
        # Remove the ROIs from the canvas
        for row in range(first, last + 1):
            roi = self.roi_model.getRoi(row)
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
            roi = self.roi_model.getRoi(index.row())
            if visual := self._roi_visuals.get(roi):
                visual.set_selected(False)
        for index in selected.indexes():
            roi = self.roi_model.getRoi(index.row())
            if visual := self._roi_visuals.get(roi):
                visual.set_selected(True)

    def _on_rows_inserted(self, parent: QModelIndex, first: int, last: int) -> None:
        for row in range(first, last + 1):
            roi = self.roi_model.getRoi(row)
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
        toolbar.addActions(self.roi_manager.mode_actions.actions())

        # LAYOUT

        layout = QHBoxLayout(self)
        left = QVBoxLayout()
        left.addWidget(toolbar)
        left.addWidget(canvas.native)
        layout.addLayout(left)
        layout.addWidget(self.roi_list)

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
