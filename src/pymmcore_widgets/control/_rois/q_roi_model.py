from __future__ import annotations

from typing import Any

from qtpy.QtCore import QAbstractListModel, QByteArray, QModelIndex, QObject, Qt

from pymmcore_widgets.control._rois.roi_model import ROI

NULL_INDEX = QModelIndex()


class QROIModel(QAbstractListModel):
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
        return roles  # type: ignore[no-any-return]

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
        elif role == self.VERTEX_ROLE:
            return roi.vertices
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

    def clear(self) -> None:
        """Clears the list of ROIs."""
        n = self.rowCount()
        if n > 0:
            self.beginRemoveRows(QModelIndex(), 0, n - 1)
            self._rois.clear()
            self.endRemoveRows()

    def pick_rois(self, point: tuple[float, float]) -> list[ROI]:
        """Return a list of ROIs that contain the given point."""
        return [roi for roi in self._rois if roi.contains(point)]
