"""
flatten_proxy_demo.py
Run with:  python flatten_proxy_demo.py.
"""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets


class TreeFlatteningProxyModel(QtCore.QAbstractProxyModel):
    """
    Proxy that flattens a tree model so that every node at `row_depth`
    appears as one row in a table.  Column 0 shows that node itself,
    column 1 its parent, column 2 its grand-parent, and so on up to the root.
    """

    def __init__(
        self, row_depth: int = 0, parent: QtCore.QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._row_depth: int = row_depth
        self._rows: list[QtCore.QModelIndex] = []

    # ------------- public API -------------------------------------------------
    def set_row_depth(self, depth: int) -> None:
        if depth != self._row_depth:
            self._row_depth = depth
            self._rebuild_row_map()

    def row_depth(self) -> int:
        return self._row_depth

    # ------------- QAbstractProxyModel overrides -----------------------------
    def setSourceModel(  # type: ignore[override]
        self, source_model: QtCore.QAbstractItemModel | None
    ) -> None:
        super().setSourceModel(source_model)
        self._rebuild_row_map()

    # ---- structure
    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        if parent.isValid() or not self.sourceModel():
            return 0
        # columns = row_depth + 1 (node itself + ancestors)
        return self._row_depth + 1

    def index(
        self,
        row: int,
        column: int,
        parent: QtCore.QModelIndex = QtCore.QModelIndex(),
    ) -> QtCore.QModelIndex:
        if parent.isValid() or not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()
        src_index = self._rows[row]
        return self.createIndex(
            row, column, src_index
        )  # internalPointer holds source index

    def parent(self, _: QtCore.QModelIndex) -> QtCore.QModelIndex:
        return QtCore.QModelIndex()  # flat table has no parents

    # ---- mapping
    def mapToSource(self, proxy_index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        return (
            proxy_index.internalPointer()
            if proxy_index.isValid()
            else QtCore.QModelIndex()
        )

    def mapFromSource(self, source_index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        try:
            row = self._rows.index(source_index)
            return self.createIndex(row, 0, source_index)
        except ValueError:
            return QtCore.QModelIndex()

    # ---- data
    def data(
        self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole
    ):
        if not index.isValid() or role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None

        src = self.mapToSource(index)
        # walk up the tree: column 0 -> node, column 1 -> parent, etc.
        node = src
        for _ in range(index.column()):
            node = node.parent()
        return self.sourceModel().data(node, role)  # type: ignore[arg-type]

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = QtCore.Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == QtCore.Qt.Orientation.Horizontal
            and role == QtCore.Qt.ItemDataRole.DisplayRole
        ):
            return f"Level {self._row_depth - section}"
        return self.sourceModel().headerData(section, orientation, role)  # type: ignore[arg-type]

    # ------------- internal helpers ------------------------------------------
    def _rebuild_row_map(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        if src := self.sourceModel():
            self._collect_rows(QtCore.QModelIndex(), 0, src)
        self.endResetModel()

    def _collect_rows(
        self,
        parent: QtCore.QModelIndex,
        depth: int,
        model: QtCore.QAbstractItemModel,
    ) -> None:
        if depth == self._row_depth:
            for r in range(model.rowCount(parent)):
                self._rows.append(model.index(r, 0, parent))
            return
        for r in range(model.rowCount(parent)):
            child = model.index(r, 0, parent)
            self._collect_rows(child, depth + 1, model)


# -----------------------------------------------------------------------------
# demo helpers
# -----------------------------------------------------------------------------
def build_tree_model() -> QtGui.QStandardItemModel:
    """Create a simple 5-level tree: A-i / B-j / C-k / D-l / E-m."""
    model = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels(["Name"])
    for ai in range(2):  # A0, A1
        item_a = QtGui.QStandardItem(f"A{ai}")
        for bj in range(2):
            item_b = QtGui.QStandardItem(f"B{ai}{bj}")
            for ck in range(2):
                item_c = QtGui.QStandardItem(f"C{ai}{bj}{ck}")
                for dl in range(2):
                    item_d = QtGui.QStandardItem(f"D{ai}{bj}{ck}{dl}")
                    for em in range(2):
                        item_e = QtGui.QStandardItem(f"E{ai}{bj}{ck}{dl}{em}")
                        item_d.appendRow(item_e)
                    item_c.appendRow(item_d)
                item_b.appendRow(item_c)
            item_a.appendRow(item_b)
        model.appendRow(item_a)
    return model


class MainWindow(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Flatten proxy demo")

        # source tree
        src_model = build_tree_model()
        tree = QtWidgets.QTreeView()
        tree.setModel(src_model)
        tree.setHeaderHidden(False)
        tree.expandAll()

        # proxy + table view
        self.proxy = TreeFlatteningProxyModel(row_depth=4)
        self.proxy.setSourceModel(src_model)

        sort_filter = QtCore.QSortFilterProxyModel()
        sort_filter.setSourceModel(self.proxy)
        sort_filter.setDynamicSortFilter(True)

        table = QtWidgets.QTableView()
        table.setModel(sort_filter)
        table.setSortingEnabled(True)
        table.horizontalHeader().setStretchLastSection(True)

        # depth selector
        depth_selector = QtWidgets.QComboBox()
        depth_selector.addItems(
            [
                "Rows = level E (depth 4)",
                "Rows = level D (depth 3)",
                "Rows = level C (depth 2)",
                "Rows = level B (depth 1)",
            ]
        )
        depth_selector.setCurrentIndex(0)

        depth_selector.currentIndexChanged.connect(
            lambda i: self.proxy.set_row_depth(4 - i)
        )

        # layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Source tree"))
        layout.addWidget(tree, 2)
        layout.addWidget(QtWidgets.QLabel("Flattened table (sortable)"))
        layout.addWidget(table, 3)
        layout.addWidget(QtWidgets.QLabel("Choose row depth"))
        layout.addWidget(depth_selector)


def main() -> None:
    import sys

    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.resize(800, 600)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
