from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeAlias, cast
from uuid import UUID, uuid4

import numpy as np
from qtpy.QtCore import (
    QAbstractListModel,
    QByteArray,
    QEvent,
    QItemSelection,
    QItemSelectionModel,
    QModelIndex,
    QObject,
    QPointF,
    Qt,
)
from qtpy.QtGui import QKeyEvent, QMouseEvent
from qtpy.QtWidgets import QApplication, QHBoxLayout, QListView, QWidget
from vispy import color
from vispy.scene import Compound, Markers, Polygon, SceneCanvas, ViewBox

if TYPE_CHECKING:
    from vispy.scene.subscene import SubScene

NULL_INDEX = QModelIndex()


@dataclass(eq=False)
class ROIBase:
    """A simple ROI class."""

    text: str = "ROI"
    selected: bool = False
    border_color: str = "#F0F66C"
    border_width: int = 2
    fill_color: str = "transparent"
    font_color: str = "yellow"
    font_size: int = 12

    _uuid: UUID = field(default_factory=uuid4, init=False, repr=False)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ROIBase) and self._uuid == other._uuid

    def __hash__(self) -> int:
        return hash(self._uuid)

    def contains(self, point: tuple[float, float]) -> bool:
        """Test if `point` lies inside this ROI."""
        raise NotImplementedError

    def bbox(self) -> tuple[float, float, float, float]:
        xs, ys = zip(*self.vertices)
        return min(xs), min(ys), max(xs), max(ys)


@dataclass(eq=False)
class PolygonROI(ROIBase):
    vertices: np.typing.ArrayLike = field(default_factory=list)

    def contains(self, point: tuple[float, float]) -> bool:
        """Standard even-odd rule ray-crossing test."""
        x, y = point
        inside = False
        verts = np.asarray(self.vertices)
        n = len(verts)
        for i in range(n):
            xi, yi = verts[i]
            xj, yj = verts[(i + 1) % n]
            # edge crosses horizontal ray at y?
            if (yi > y) != (yj > y):
                # compute x coordinate of intersection
                x_int = xi + (y - yi) * (xj - xi) / (yj - yi)
                if x < x_int:
                    inside = not inside
        return inside


@dataclass(eq=False)
class RectangleROI(ROIBase):
    """A rectangle ROI class."""

    top_left: tuple[int, int] = (0, 0)
    bot_right: tuple[int, int] = (0, 0)

    @property
    def vertices(self) -> list[tuple[int, int]]:
        """Return the vertices of the rectangle ROI."""
        return [
            (self.top_left[0], self.top_left[1]),
            (self.bot_right[0], self.top_left[1]),
            (self.bot_right[0], self.bot_right[1]),
            (self.top_left[0], self.bot_right[1]),
        ]

    def contains(self, point: tuple[float, float]) -> bool:
        """Test if `point` lies inside this rectangle ROI."""
        x, y = point
        x0, y0 = self.top_left
        x1, y1 = self.bot_right
        return x0 <= x <= x1 and y0 <= y <= y1


ROI: TypeAlias = "PolygonROI | RectangleROI"


class QROIManager(QAbstractListModel):
    """A QAbstractListModel for ROIs."""

    ROI_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rois: list[ROI] = []

    # Read only stuff ------------------------------

    def roleNames(self) -> dict[int, QByteArray]:
        """Return a dictionary of role names for the model."""
        roles = super().roleNames()
        roles[self.ROI_ROLE] = QByteArray(b"roi")
        return roles

    def rowCount(self, parent: QModelIndex = NULL_INDEX) -> int:
        return len(self._rois)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        roi = self._rois[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return roi.text
        elif role == self.ROI_ROLE:
            return roi
        else:
            return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Return data for `role` and `section` in the header at `orientation`."""
        return super().headerData(section, orientation, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Returns the item flags for the given index.

        When editable, return value must also include ItemIsEditable.
        """
        flags = super().flags(index)
        if index.isValid():
            flags |= Qt.ItemFlag.ItemIsEditable
            flags |= Qt.ItemFlag.ItemIsEnabled
            flags |= Qt.ItemFlag.ItemIsSelectable
            flags |= Qt.ItemFlag.ItemIsDropEnabled
        return flags

    # editable stuff ------------------------------

    def setData(
        self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        """Sets the role data for the item at index to value.

        Returns true if successful; otherwise returns false.
        """
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        roi = self._rois[index.row()]
        roi.text = value
        return True

    def index(
        self, row: int, column: int = 0, parent: QModelIndex = NULL_INDEX
    ) -> QModelIndex:
        """Returns the index of the item at row and column under parent.

        The base class implementation returns an invalid index if the item does not
        exist.
        """
        if not (0 <= row < len(self._rois)) or column != 0:
            return NULL_INDEX
        # attach the roi to the index
        return self.createIndex(row, column, self._rois[row])

    def index_of(self, roi: ROI) -> QModelIndex:
        """Returns the index of the given ROI."""
        for i, r in enumerate(self._rois):
            if r == roi:
                return self.index(i)
        return NULL_INDEX

    # resize stuff ------------------------------

    def insertRows(
        self, row: int, count: int, parent: QModelIndex = NULL_INDEX
    ) -> bool:
        """Inserts `count` rows before the given row."""
        self.beginInsertRows(parent, row, row + count - 1)
        for _ in range(count):
            self._rois.insert(row, PolygonROI())
        self.endInsertRows()
        return True

    def removeRows(
        self, row: int, count: int, parent: QModelIndex = NULL_INDEX
    ) -> bool:
        """Removes `count` rows starting with `row` under `parent`.

        Returns true if the rows were successfully removed; otherwise returns false.

        The base class implementation does nothing and returns false.
        """
        self.beginRemoveRows(parent, row, row + count - 1)
        for _ in range(count):
            self._rois.pop(row)
        self.endRemoveRows()
        return True

    def addROI(self, roi: ROI | None = None) -> ROI:
        """Adds a new ROI to the list."""
        roi = roi or PolygonROI()
        self.beginInsertRows(NULL_INDEX, len(self._rois), len(self._rois))
        self._rois.append(roi)
        self.endInsertRows()
        return roi

    def removeROI(self, roi: ROI) -> None:
        """Removes the given ROI from the list."""
        for i, r in enumerate(self._rois):
            if r == roi:
                self.beginRemoveRows(NULL_INDEX, i, i)
                self._rois.pop(i)
                self.endRemoveRows()
                break
        else:
            raise ValueError("ROI not found in list")

    def pick_rois(self, point: tuple[float, float]) -> list[ROI]:
        """Return a list of ROIs that contain the given point."""
        return [roi for roi in self._rois if roi.contains(point)]


class RoiPolygon(Compound):
    """A vispy visual for the ROI."""

    def __init__(self, roi: ROI) -> None:
        self._roi = roi
        verts = np.asarray(roi.vertices)
        self._polygon = Polygon(
            pos=verts,
            color=roi.fill_color,
            border_color=roi.border_color,
            border_width=roi.border_width,
        )
        self._handles = Markers(
            pos=verts,
            size=10,
            scaling=False,  # "fixed"
            face_color=color.Color("white"),
        )
        self._handles.visible = roi.selected

        super().__init__([self._polygon, self._handles])

    def update_from_roi(self, roi: ROI) -> None:
        self.pos = roi.vertices
        self._polygon.color = roi.fill_color
        self._polygon.border_color = roi.border_color
        self._polygon._border_width = roi.border_width
        self.set_selected(roi.selected)

    def set_selected(self, selected: bool) -> None:
        self._roi.selected = selected
        self._handles.visible = selected


class ROIScene(QWidget):
    def __init__(self, canvas: SceneCanvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ROI Manager")
        self.setGeometry(100, 100, 800, 600)
        for child in canvas.central_widget.children:
            if isinstance(child, ViewBox):
                self.view = child
                break
        else:
            self.view = canvas.central_widget.add_view(camera="panzoom")

        self.roi_list = QListView()
        self.roi_list.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.model = QROIManager()
        self.roi_list.setModel(self.model)

        self._canvas = canvas
        canvas.native.installEventFilter(self)
        self.roi_list.installEventFilter(self)

        self._roi_visuals: dict[ROI, RoiPolygon] = {}

        layout = QHBoxLayout(self)
        layout.addWidget(canvas.native)
        layout.addWidget(self.roi_list)

        self.model.rowsInserted.connect(self._on_rows_inserted)
        self.model.rowsAboutToBeRemoved.connect(self._on_rows_about_to_be_removed)
        self.model.dataChanged.connect(self._on_data_changed)
        self._selection_model = cast(
            "QItemSelectionModel", self.roi_list.selectionModel()
        )
        self._selection_model.selectionChanged.connect(self._on_selection_changed)

    def canavs_to_world(self, point: QPointF) -> tuple[float, float]:
        """Convert a point from canvas coordinates to world coordinates."""
        return tuple(self.view.scene.transform.imap((point.x(), point.y()))[:2])

    def eventFilter(self, source: QObject | None, event: QEvent | None) -> bool:
        """Filter events for the ROI list."""
        if not event:
            return False

        if isinstance(event, QMouseEvent):
            if event.type() == QEvent.Type.MouseButtonPress:
                # when the left mouse button is pressed, select the ROI
                world_point = self.canavs_to_world(event.position())
                self._selection_model.clearSelection()
                for roi in self.model.pick_rois(world_point):
                    self._selection_model.select(
                        self.model.index_of(roi),
                        QItemSelectionModel.SelectionFlag.Select
                        | QItemSelectionModel.SelectionFlag.Rows,
                    )
                return True

        if isinstance(event, QKeyEvent):
            # when the delete key is pressed, remove the selected ROIs
            if (
                event.type() == QEvent.Type.KeyPress
                and not event.isAutoRepeat()
                and event.key() == Qt.Key.Key_Backspace
            ):
                self._delete_selected_rois()
                return True

            # never pass key events to the canvas
            if source is self._canvas.native:
                event.ignore()
                return True

        return super().eventFilter(source, event)

    def _delete_selected_rois(self) -> None:
        """Delete the selected ROIs from the model."""
        if sel := self._selection_model.selectedIndexes():
            rows = [index.row() for index in sel]
            for row in sorted(rows, reverse=True):
                self.model.removeRows(row, 1)

    @property
    def _scene(self) -> SubScene:
        return self.view.scene

    def _reset_range(self) -> None:
        """Reset the camera range to fit all ROIs."""
        if self._scene.children:
            self.view.camera.set_range()

    def _on_rows_about_to_be_removed(
        self, parent: QModelIndex, first: int, last: int
    ) -> None:
        # Remove the ROIs from the canvas
        for row in range(first, last + 1):
            roi = self.model.index(row).internalPointer()
            self._remove_roi_from_canvas(roi)

    def _on_data_changed(
        self, top_left: QModelIndex, bottom_right: QModelIndex, roles: list[int]
    ) -> None:
        # Update the ROI on the canvas
        for row in range(top_left.row(), bottom_right.row() + 1):
            roi = self.model.index(row).internalPointer()
            self._update_roi_visual(roi)

    def _on_selection_changed(
        self, selected: QItemSelection, deselected: QItemSelection
    ) -> None:
        for index in deselected.indexes():
            roi = cast("ROI", self.model.index(index.row()).internalPointer())
            if visual := self._roi_visuals.get(roi):
                visual.set_selected(False)
        for index in selected.indexes():
            roi = cast("ROI", self.model.index(index.row()).internalPointer())
            if visual := self._roi_visuals.get(roi):
                visual.set_selected(True)

    def _on_rows_inserted(self, parent: QModelIndex, first: int, last: int) -> None:
        # how do I actually add the new ROIs to the canvas here?
        for row in range(first, last + 1):
            roi = self.model.index(row).internalPointer()
            self._add_roi_to_canvas(roi)
        self._reset_range()

    def _add_roi_to_canvas(self, roi: ROI) -> None:
        # Create a polygon visual for the ROI
        self._roi_visuals[roi] = polygon = RoiPolygon(roi)
        polygon.parent = self.view.scene

    def _remove_roi_from_canvas(self, roi: ROI) -> None:
        # Remove the ROI from the canvas
        if visual := self._roi_visuals.pop(roi, None):
            visual.parent = None

    def _update_roi_visual(self, roi: ROI) -> None:
        # Update the ROI visual already on the canvas
        if visual := self._roi_visuals.get(roi):
            visual.update_from_roi(roi)


if __name__ == "__main__":
    app = QApplication([])
    canvas = SceneCanvas()
    scene = ROIScene(canvas)
    scene.show()
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
            roi = PolygonROI(vertices=np.random.rand(npoints, 2) * 100)
        scene.model.addROI(roi).text = f"ROI {i + 1}"
    app.exec()
