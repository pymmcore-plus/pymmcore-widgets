from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast
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
from qtpy.QtGui import QCursor, QKeyEvent, QMouseEvent
from qtpy.QtWidgets import QApplication, QHBoxLayout, QListView, QWidget
from vispy import color
from vispy.scene import Compound, Markers, Polygon, SceneCanvas, ViewBox

if TYPE_CHECKING:
    from vispy.scene.subscene import SubScene

NULL_INDEX = QModelIndex()


@dataclass(eq=False)
class ROI:
    """A polygonal ROI."""

    vertices: np.ndarray = field(default_factory=list)  # type: ignore[arg-type]
    text: str = "ROI"
    selected: bool = False
    border_color: str = "#F0F66C"
    border_width: int = 2
    fill_color: str = "transparent"
    font_color: str = "yellow"
    font_size: int = 12

    def translate(self, dx: float, dy: float) -> None:
        """Translate the ROI in place by (dx, dy)."""
        self.vertices = self.vertices + np.array([dx, dy], dtype=self.vertices.dtype)

    def __post_init__(self) -> None:
        self.vertices = np.asarray(self.vertices).astype(np.float32)
        if self.vertices.ndim != 2 or self.vertices.shape[1] != 2:
            raise ValueError("Vertices must be a 2D array of shape (n, 2)")

    _uuid: UUID = field(default_factory=uuid4, init=False, repr=False)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ROI) and self._uuid == other._uuid

    def __hash__(self) -> int:
        return hash(self._uuid)

    def bbox(self) -> tuple[float, float, float, float]:
        """Return the bounding box of this ROI."""
        (x0, y0) = self.vertices.min(axis=0)
        (x1, y1) = self.vertices.max(axis=0)
        return float(x0), float(y0), float(x1), float(y1)

    def contains(self, point: tuple[float, float]) -> bool:
        """Return True if `point` lies inside this ROI."""
        x0, y0, x1, y1 = self.bbox()
        if not (x0 <= point[0] <= x1 and y0 <= point[1] <= y1):
            return False
        return self._inner_contains(point)

    def _inner_contains(self, point: tuple[float, float]) -> bool:
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

    def translate_vertex(self, idx: int, dx: float, dy: float) -> None:
        """Move a vertex of the ROI by (dx, dy), in place."""
        if not (0 <= idx < len(self.vertices)):
            raise IndexError("Vertex index out of range")
        self.vertices[idx] += np.array([dx, dy], dtype=self.vertices.dtype)


@dataclass(eq=False)
class RectangleROI(ROI):
    """A rectangle ROI class."""

    def __init__(
        self,
        top_left: tuple[float, float],
        bot_right: tuple[float, float],
        **kwargs: Any,
    ) -> None:
        """Create a rectangle ROI.

        Vertices are defined in the order:
        top-left, bottom-left, bottom-right, top-right.

        Parameters
        ----------
        top_left : tuple[float, float]
            The top left corner of the rectangle.
        bot_right : tuple[float, float]
            The bottom right corner of the rƒectangle.
        **kwargs : Any
            Additional keyword arguments to pass to the base class.
        """
        left, top = top_left
        right, bottom = bot_right
        vertices = np.array([top_left, (left, bottom), bot_right, (right, top)])
        super().__init__(vertices=vertices, **kwargs)

    @property
    def top_left(self) -> tuple[float, float]:
        """Return the top left corner of the rectangle."""
        return self.vertices[0]  # type: ignore[no-any-return]

    @property
    def bot_right(self) -> tuple[float, float]:
        """Return the bottom right corner of the rectangle."""
        return self.vertices[2]  # type: ignore[no-any-return]

    @property
    def width(self) -> float:
        """Return the width of the rectangle."""
        return self.bot_right[0] - self.top_left[0]

    @property
    def height(self) -> float:
        """Return the height of the rectangle."""
        return self.bot_right[1] - self.top_left[1]

    def translate_vertex(self, idx: int, dx: float, dy: float) -> None:
        """Move a vertex of the rectangle by (dx, dy).

        The rectangle is resized to remain rectangular.
        The two adjacent vertices are moved along with the dragged vertex.
        """
        vs = self.vertices
        # bump the clicked corner
        vs[idx][0] += dx
        vs[idx][1] += dy
        # the “other” corner on the same vertical edge: idx ^ 1
        vs[idx ^ 1][0] += dx
        # the “other” corner on the same horizontal edge: idx ^ 3
        vs[idx ^ 3][1] += dy


class QROIManager(QAbstractListModel):
    """A QAbstractListModel for ROIs."""

    ROI_ROLE = Qt.ItemDataRole.UserRole + 1
    VERTEX_ROLE = Qt.ItemDataRole.UserRole + 2

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
            self._rois.insert(row, ROI())
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
        roi = roi or ROI()
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

    def update_vertices(self, vertices: np.ndarray) -> None:
        """Update the vertices of the polygon."""
        self._polygon.pos = vertices
        self._handles.set_data(pos=vertices)

    def update_from_roi(self, roi: ROI) -> None:
        self._polygon.color = roi.fill_color
        self._polygon.border_color = roi.border_color
        self._polygon._border_width = roi.border_width

        self.update_vertices(roi.vertices)
        self.set_selected(roi.selected)

    def set_selected(self, selected: bool) -> None:
        self._roi.selected = selected
        self._handles.visible = selected


class CanvasEventFilter(QObject):
    """A QObject that filters events for a canvas."""

    def __init__(self, parent: ROIScene) -> None:
        super().__init__(parent)
        self._scene_widget = parent
        self.view = parent.view
        self.roi_manager = parent.roi_manager
        self.selection_model = parent._selection_model

        self._drag_roi: ROI | None = None
        self._drag_vertex_idx: int | None = None
        self._drag_start: tuple[float, float] = (0.0, 0.0)

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
            if event.type() == QEvent.Type.MouseButtonPress:
                return self._handle_mouse_press(event)
            if event.type() == QEvent.Type.MouseMove:
                if event.buttons() == Qt.MouseButton.NoButton:
                    return self._handle_mouse_hover(event, source)  # type: ignore
                else:
                    return self._handle_mouse_move(event)
            if event.type() == QEvent.Type.MouseButtonRelease:
                return self._handle_mouse_release(event)

        return False

    def _handle_key_press(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Backspace:
            # delete selected ROIs
            self._scene_widget._delete_selected_rois()

    def _handle_mouse_press(self, event: QMouseEvent) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        click_pt = event.position()
        # world-coords for ROI tests
        wp = self._scene_widget.canvas_to_world(click_pt)

        # 1) try per-vertex hit in _pixel_ space
        if (vertex := self._vertex_under_pointer(event)) is not None:
            # start a vertex-drag
            self._drag_roi, self._drag_vertex_idx = vertex
            self._drag_start = wp
            return True

        self.selection_model.clearSelection()
        hits = self.roi_manager.pick_rois(wp)
        # 2) fallback to whole-ROI drag if clicked inside
        if hits:
            roi = hits[0]
            self._drag_roi = roi
            self._drag_vertex_idx = None
            self._drag_start = wp
            self.selection_model.select(
                self.roi_manager.index_of(roi),
                QItemSelectionModel.SelectionFlag.ClearAndSelect,
            )
            return True

        # else let the canvas handle panning
        self._drag_roi = None
        return False

    def _vertex_under_pointer(self, event: QMouseEvent) -> tuple[ROI, int] | None:
        """Return the index of the vertex under the pointer, or None."""
        for roi in self._scene_widget.selected_rois():
            if (vertex_idx := self._find_vertex(event.position(), roi)) is not None:
                return roi, vertex_idx
        return None

    def _handle_mouse_hover(self, event: QMouseEvent, source: QWidget) -> bool:
        # check for handle under pointer
        if self._vertex_under_pointer(event) is not None:
            source.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        else:
            source.unsetCursor()
        return False

    def _handle_mouse_move(self, event: QMouseEvent) -> bool:
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_roi:
            wp = self._scene_widget.canvas_to_world(event.position())
            dx = wp[0] - self._drag_start[0]
            dy = wp[1] - self._drag_start[1]

            if self._drag_vertex_idx is not None:
                # move only the dragged vertex
                self._drag_roi.translate_vertex(self._drag_vertex_idx, dx, dy)
            else:
                # move the entire ROI
                self._drag_roi.translate(dx, dy)

            self._drag_start = wp
            idx = self.roi_manager.index_of(self._drag_roi)
            self.roi_manager.dataChanged.emit(idx, idx, [self.roi_manager.VERTEX_ROLE])
            return True

        return False

    def _handle_mouse_release(self, event: QMouseEvent) -> bool:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_roi:
            self._drag_roi = None
            self._drag_vertex_idx = None
            return True
        return False

    def _find_vertex(self, sp: QPointF, roi: ROI) -> int | None:
        """Return index of roi vertex under screen-pos `sp`, or None."""
        # map the ROI vertices to screen coords
        # rather than converting the point to world... this avoids issues with zoom
        data = roi.vertices  # shape (N,2)
        pts = np.column_stack([data, np.zeros(len(data))])
        screen_vertices = self.view.scene.transform.map(pts)[:, :2]

        # find the closest vertex to the screen position
        d2 = np.sum((screen_vertices - np.array([sp.x(), sp.y()])) ** 2, axis=1)
        idx = int(np.argmin(d2))
        if d2[idx] <= self._handle_pick_tol**2:
            return idx
        return None


class ROIScene(QWidget):
    def __init__(self, canvas: SceneCanvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ROI Manager")
        self.setGeometry(100, 100, 800, 600)

        # create a viewbox if one doesn't exist
        for child in canvas.central_widget.children:
            if isinstance(child, ViewBox):
                self.view = child
                break
        else:
            self.view = canvas.central_widget.add_view(camera="panzoom")

        self.roi_manager = QROIManager()

        self.roi_list = QListView()
        self.roi_list.setModel(self.roi_manager)
        self.roi_list.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.roi_list.installEventFilter(self)
        self._selection_model = cast(
            "QItemSelectionModel", self.roi_list.selectionModel()
        )

        self._canvas = canvas
        self._canvas_filter = CanvasEventFilter(self)
        canvas.native.installEventFilter(self._canvas_filter)

        self._roi_visuals: dict[ROI, RoiPolygon] = {}

        self.roi_manager.rowsInserted.connect(self._on_rows_inserted)
        self.roi_manager.rowsAboutToBeRemoved.connect(self._on_rows_about_to_be_removed)
        self.roi_manager.dataChanged.connect(self._on_data_changed)
        self._selection_model.selectionChanged.connect(self._on_selection_changed)

        # LAYOUT

        layout = QHBoxLayout(self)
        layout.addWidget(canvas.native)
        layout.addWidget(self.roi_list)

    def canvas_to_world(self, point: QPointF) -> tuple[float, float]:
        """Convert a point from canvas coordinates to world coordinates."""
        return tuple(self.view.scene.transform.imap((point.x(), point.y()))[:2])

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
                self._delete_selected_rois()
                return True

            # never pass key events to the canvas
            if source is self._canvas.native:
                event.ignore()
                return True

        return super().eventFilter(source, event)

    def selected_rois(self) -> list[ROI]:
        """Return a list of selected ROIs."""
        return [
            cast("ROI", self.roi_manager.index(index.row()).internalPointer())
            for index in self._selection_model.selectedIndexes()
        ]

    def _delete_selected_rois(self) -> None:
        """Delete the selected ROIs from the model."""
        for roi in self.selected_rois():
            self.roi_manager.removeROI(roi)

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
            roi = self.roi_manager.index(row).internalPointer()
            self._remove_roi_from_canvas(roi)

    def _on_data_changed(
        self, top_left: QModelIndex, bottom_right: QModelIndex, roles: list[int]
    ) -> None:
        if set(roles) == {self.roi_manager.VERTEX_ROLE}:
            do_update = self._update_roi_vertices
        else:
            do_update = self._update_roi_visual

        # Update the ROI on the canvas
        for row in range(top_left.row(), bottom_right.row() + 1):
            roi = self.roi_manager.index(row).internalPointer()
            do_update(roi)

    def _on_selection_changed(
        self, selected: QItemSelection, deselected: QItemSelection
    ) -> None:
        for index in deselected.indexes():
            roi = cast("ROI", self.roi_manager.index(index.row()).internalPointer())
            if visual := self._roi_visuals.get(roi):
                visual.set_selected(False)
        for index in selected.indexes():
            roi = cast("ROI", self.roi_manager.index(index.row()).internalPointer())
            if visual := self._roi_visuals.get(roi):
                visual.set_selected(True)

    def _on_rows_inserted(self, parent: QModelIndex, first: int, last: int) -> None:
        # how do I actually add the new ROIs to the canvas here?
        for row in range(first, last + 1):
            roi = self.roi_manager.index(row).internalPointer()
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
        # Update the the full ROI visual already on the canvas
        if visual := self._roi_visuals.get(roi):
            visual.update_from_roi(roi)

    def _update_roi_vertices(self, roi: ROI) -> None:
        # Update the only vertices of the ROI visual
        if visual := self._roi_visuals.get(roi):
            visual.update_vertices(roi.vertices)


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
            roi = ROI(vertices=np.random.rand(npoints, 2) * 100)
        scene.roi_manager.addROI(roi).text = f"ROI {i + 1}"
    app.exec()
