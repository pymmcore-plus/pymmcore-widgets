from __future__ import annotations

from typing import Any

from qtpy.QtCore import QAbstractItemModel, QModelIndex, QSortFilterProxyModel, Qt


class CheckedProxy(QSortFilterProxyModel):
    """Proxy model that keeps only rows with at least one *checked* item.

    If check_column is `-1`, all columns in the row are inspected, otherwise
    only the specified column is checked.

    Parameters
    ----------
    check_column
        Column index on which to look for the check state.  Use `-1` to
        inspect *all* columns in the row.
    include_partially_checked
        If `True`, rows with `Qt.PartiallyChecked` will also be kept.
    """

    def __init__(
        self,
        check_column: int = -1,
        *,
        include_partially_checked: bool = False,
        parent: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self._check_column = check_column
        self._include_partial = include_partially_checked

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        src = self.sourceModel()
        if src is None:
            return False

        # 1. Check the current row
        cols = (
            range(src.columnCount(source_parent))
            if self._check_column < 0
            else [self._check_column]
        )
        for col in cols:
            idx = src.index(source_row, col, source_parent)
            state = idx.data(Qt.ItemDataRole.CheckStateRole)
            if state == Qt.CheckState.Checked or (
                state == Qt.CheckState.PartiallyChecked and self._include_partial
            ):
                return True
        # 2. If not checked, keep the row if *any* descendant is checked
        child_parent = src.index(source_row, 0, source_parent)
        for i in range(src.rowCount(child_parent)):
            if self.filterAcceptsRow(i, child_parent):
                return True

        return False

    def setSourceModel(self, model: QAbstractItemModel | None) -> None:
        super().setSourceModel(model)
        if model is not None:  # refresh when check states change
            model.dataChanged.connect(self.invalidate)
