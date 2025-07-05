from __future__ import annotations

from collections import defaultdict
from typing import Any

from PyQt6 import QtCore, QtGui, QtWidgets


class FlattenModel(QtCore.QSortFilterProxyModel):
    """A proxy model that flattens a tree model into a table view with expandable rows.

    This model allows you to specify a row depth, which determines how many rows are
    shown in the flattened view. For example, if row_depth=0, it reverts to the original
    model, while row_depth=1 shows the first level of children, and row_depth=2 shows
    the second level of children. The model supports expandable rows, allowing users to
    expand and collapse child rows based on the specified depth.
    """

    def __init__(
        self, row_depth: int = 0, parent: QtCore.QObject | None = None
    ) -> None:
        super().__init__(parent)
        # the row depth determines how many rows we show in the flattened view
        # for example, if row_depth=0, we revert to the original model,
        self._row_depth = row_depth
        # Store which rows are expandable and their children
        self._expandable_rows: dict[int, list[list[tuple[int, int]]]] = {}

    def set_row_depth(self, row_depth: int) -> None:
        """Set the row depth for the flattened view."""
        self._row_depth = row_depth
        self._rebuild()

    # ------------- QAbstractItemModel interface methods -------------

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = QtCore.Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Return the header data for the given section and orientation."""
        if (
            orientation == QtCore.Qt.Orientation.Horizontal
            and role == QtCore.Qt.ItemDataRole.DisplayRole
        ):
            return f"Level {section}"  # Level 0 = root, Level N = leaf
        return super().headerData(section, orientation, role)

    def rowCount(self, parent: QtCore.QModelIndex | None = None) -> int:
        """Return the number of rows under the given parent."""
        if parent is None:
            parent = QtCore.QModelIndex()
        if self._row_depth <= 0:
            return super().rowCount(parent)

        if not parent.isValid():
            # Top-level: return number of primary flattened rows
            return len(self._row_paths)

        # For a parent row, return number of children if expandable
        if parent.internalId() == 0:  # Top-level row
            parent_row = parent.row()
            if parent_row in self._expandable_rows:
                return len(self._expandable_rows[parent_row])
        return 0

    def hasChildren(self, parent: QtCore.QModelIndex | None = None) -> bool:
        """Return whether the given index has children."""
        return bool(self.rowCount(parent))

    def columnCount(self, parent: QtCore.QModelIndex | None = None) -> int:
        """Return the number of columns for the given parent."""
        if parent is None:
            parent = QtCore.QModelIndex()
        if self._row_depth <= 0:
            return super().columnCount(parent)

        # For flattened view, show columns up to row_depth + 1
        # This makes row_depth=1 show 2 columns, row_depth=2 show 3 columns, etc.
        return self._row_depth + 1

    def setSourceModel(self, source_model: QtCore.QAbstractItemModel | None) -> None:
        """Set the source model and rebuild the flattened view."""
        super().setSourceModel(source_model)
        if source_model:
            source_model.dataChanged.connect(self._rebuild)
        self._rebuild()

    def index(
        self,
        row: int,
        column: int,
        parent: QtCore.QModelIndex | None = None,
    ) -> QtCore.QModelIndex:
        """Returns the index of the item specified by (row, column, parent)."""
        if parent is None:
            parent = QtCore.QModelIndex()
        if self._row_depth <= 0:
            return super().index(row, column, parent)

        if not parent.isValid():
            # Top-level rows (the primary flattened rows)
            if row < 0 or row >= len(self._row_paths):
                return QtCore.QModelIndex()
            if column < 0 or column >= self.columnCount():
                return QtCore.QModelIndex()
            return self.createIndex(row, column, 0)  # 0 indicates top-level
        else:
            # Child rows (expanded children of a parent row)
            parent_row = parent.row()
            if parent_row in self._expandable_rows:
                children = self._expandable_rows[parent_row]
                if row < 0 or row >= len(children):
                    return QtCore.QModelIndex()
                # For child rows, check against the child path length, not _max_depth
                child_path = children[row]
                max_child_col = len(child_path) - 1
                if column < 0 or column > max_child_col:
                    return QtCore.QModelIndex()
                # Add bounds checking for parent_row to prevent overflow
                if parent_row < 0 or parent_row >= len(self._row_paths):
                    return QtCore.QModelIndex()
                # Use parent_row + 1 as internal pointer to identify this is a child
                return self.createIndex(row, column, parent_row + 1)
            return QtCore.QModelIndex()

    def parent(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:  # type: ignore [override]
        """Returns the parent of the given child index."""
        if self._row_depth <= 0:
            return super().parent(index)

        if not index.isValid():
            return QtCore.QModelIndex()

        internal_ptr = index.internalId()
        if internal_ptr == 0:
            # This is a top-level row, so no parent
            return QtCore.QModelIndex()
        else:
            # This is a child row, parent is at internal_ptr - 1
            parent_row = internal_ptr - 1
            # Add bounds checking to prevent overflow
            if parent_row < 0 or parent_row >= len(self._row_paths):
                # Invalid parent row, return invalid index
                return QtCore.QModelIndex()
            # Return parent at column 0 for tree structure
            return self.createIndex(parent_row, 0, 0)

    def mapToSource(self, proxy_index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        """Map from the flattened view back to the source model."""
        if self._row_depth <= 0 or not (src_model := self.sourceModel()):
            return super().mapToSource(proxy_index)

        if not proxy_index.isValid():
            return QtCore.QModelIndex()

        row, col = proxy_index.row(), proxy_index.column()
        internal_ptr = proxy_index.internalId()

        if internal_ptr == 0:
            # Top-level row: navigate to the column depth requested
            if row >= len(self._row_paths):
                return QtCore.QModelIndex()
            path = self._row_paths[row]

            if col >= len(path):  # beyond recorded depth
                return QtCore.QModelIndex()

            src = QtCore.QModelIndex()
            for r, c in path[: col + 1]:
                src = src_model.index(r, c, src)
            return src
        else:
            # Child row: these are the deeper children (C-level nodes)
            parent_row = internal_ptr - 1
            if parent_row not in self._expandable_rows:
                return QtCore.QModelIndex()
            children = self._expandable_rows[parent_row]
            if row >= len(children):
                return QtCore.QModelIndex()
            path = children[row]

            # For children, we have different behavior per column:
            if col == 0:
                # Column 0: Don't show anything for child rows (they should be indented)
                return QtCore.QModelIndex()
            elif col == self._row_depth:
                # Target depth column: show the full child data (navigate the complete path)
                src = QtCore.QModelIndex()
                for r, c in path:
                    src = src_model.index(r, c, src)
                return src
            else:
                # Other columns: no data
                return QtCore.QModelIndex()

    def mapFromSource(self, source_index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        """Map from source model back to proxy model."""
        if self._row_depth <= 0 or not (src_model := self.sourceModel()):
            return super().mapFromSource(source_index)

        if not source_index.isValid():
            return QtCore.QModelIndex()

        # Build the path from root to this source index
        path = []
        current = source_index
        while current.isValid():
            path.append((current.row(), current.column()))
            current = current.parent()
        path.reverse()  # Now path is from root to source_index

        # Check if this path matches any of our top-level rows
        for proxy_row, row_path in enumerate(self._row_paths):
            # Check if the source path starts with our row path
            if len(path) >= len(row_path):
                matches = True
                for i, (proxy_r, proxy_c) in enumerate(row_path):
                    if i >= len(path) or path[i] != (proxy_r, proxy_c):
                        matches = False
                        break

                if matches:
                    # This source index corresponds to our proxy row
                    if len(path) == len(row_path):
                        # Exact match - this is a top-level item
                        column = len(path) - 1  # Column based on depth
                        if column < self.columnCount():
                            return self.createIndex(proxy_row, column, 0)
                    elif len(path) == len(row_path) + 1:
                        # This is a child of our top-level item
                        if proxy_row in self._expandable_rows:
                            children = self._expandable_rows[proxy_row]
                            child_row_in_source = path[-1][0]  # Last element's row
                            if child_row_in_source < len(children):
                                column = len(path) - 1  # Column based on depth
                                if column < self.columnCount():
                                    return self.createIndex(
                                        child_row_in_source, column, proxy_row + 1
                                    )

        return QtCore.QModelIndex()

    def _rebuild(self) -> None:
        self.beginResetModel()
        self._max_depth = 0
        # one entry per proxy row
        self._row_paths: list[list[tuple[int, int]]] = []
        # mapping of depth -> (num_rows, num_columns)
        self._num_leaves_at_depth = defaultdict[int, int](int)
        self._expandable_rows = {}
        if src := self.sourceModel():
            self._collect_model_shape(src)
        self.endResetModel()

    def _collect_model_shape(
        self,
        model: QtCore.QAbstractItemModel,
        parent: QtCore.QModelIndex | None = None,
        depth: int = 0,
        stack: list[tuple[int, int]] | None = None,
    ) -> None:
        if parent is None:
            parent = QtCore.QModelIndex()
        if stack is None:
            stack = []

        rows = model.rowCount(parent)
        self._num_leaves_at_depth[depth] += rows
        self._max_depth = max(self._max_depth, depth)

        for r in range(rows):
            child = model.index(r, 0, parent)  # tree is in column 0
            pair_path = [*stack, (r, 0)]

            # Add node if we're at target depth OR
            # if it's a terminal node before target depth
            should_add_node = (
                depth == self._row_depth  # At target depth
                or (
                    depth < self._row_depth and not model.hasChildren(child)
                )  # Terminal before target
            )

            if should_add_node:
                # Add the row to the flattened view
                row_index = len(self._row_paths)
                self._row_paths.append(pair_path)

                # If this row has children and we're at target depth,
                # store them for expansion
                if depth == self._row_depth and model.hasChildren(child):
                    children = []
                    child_rows = model.rowCount(child)
                    for child_r in range(child_rows):
                        child_path = [*pair_path, (child_r, 0)]
                        children.append(child_path)
                    self._expandable_rows[row_index] = children

            # Continue if we haven't reached target depth and node has children
            if depth < self._row_depth and model.hasChildren(child):
                self._collect_model_shape(model, child, depth + 1, pair_path)


def build_tree_model() -> QtGui.QStandardItemModel:
    """Create a simple 5-level tree: A-i / B-j / C-k / D-l / E-m."""
    model = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels(["Name"])

    item_a0 = QtGui.QStandardItem("A0")
    model.appendRow(item_a0)
    item_a1 = QtGui.QStandardItem("A1")
    model.appendRow(item_a1)

    item_b00 = QtGui.QStandardItem("B00")
    item_a0.appendRow(item_b00)
    item_b01 = QtGui.QStandardItem("B01")
    item_a0.appendRow(item_b01)

    item_b10 = QtGui.QStandardItem("B10")
    item_a1.appendRow(item_b10)
    item_b11 = QtGui.QStandardItem("B11")
    item_a1.appendRow(item_b11)

    item_c000 = QtGui.QStandardItem("C000")
    item_b00.appendRow(item_c000)
    item_c001 = QtGui.QStandardItem("C001")
    item_b00.appendRow(item_c001)

    item_c111 = QtGui.QStandardItem("C111")
    item_b11.appendRow(item_c111)

    return model


def print_model(
    model: QtCore.QAbstractItemModel,
    parent: QtCore.QModelIndex | None = None,
    depth: int = 0,
) -> None:
    """Print the model structure to the console."""
    if parent is None:
        parent = QtCore.QModelIndex()

    rows = model.rowCount(parent)
    for r in range(rows):
        child = model.index(r, 0, parent)  # tree is in column 0
        # print an ascii tree
        print("  " * depth + f"- {model.data(child)}")
        print_model(model, child, depth + 1)


class MainWindow(QtWidgets.QWidget):
    """Main demo window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Flatten proxy demo")

        # source tree
        src_model = build_tree_model()
        print_model(src_model)

        tree1 = QtWidgets.QTreeView()
        tree1.setModel(src_model)
        tree1.expandAll()

        # proxy + table view
        self.proxy = FlattenModel(row_depth=0)
        self.proxy.setSourceModel(src_model)

        self.tree2 = tree2 = QtWidgets.QTreeView()
        tree2.setAlternatingRowColors(True)
        # tree2.setSortingEnabled(True)
        tree2.setModel(self.proxy)
        tree1.expandAll()

        # depth selector
        self.combo = depth_selector = QtWidgets.QComboBox()
        depth_selector.addItems(
            [
                "Rows = level A (depth 0)",
                "Rows = level B (depth 1)",
                "Rows = level C (depth 2)",
            ]
        )

        depth_selector.currentIndexChanged.connect(self.proxy.set_row_depth)

        # layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Source tree"))
        layout.addWidget(tree1, 2)
        layout.addWidget(QtWidgets.QLabel("Flattened table (sortable)"))
        layout.addWidget(tree2, 3)
        layout.addWidget(QtWidgets.QLabel("Choose row depth"))
        layout.addWidget(depth_selector)


def main() -> None:
    """Run the demo application."""
    import sys

    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.resize(800, 600)
    win.show()

    # PROGRAMMATICALLY INTERACT HERE

    # Expand all in the tree view to show hierarchical structure
    win.combo.setCurrentIndex(1)  # Set to depth 1 to show the improved layout
    win.tree2.expandAll()

    win.grab().save("flatten_proxy_demo.png", "PNG")
    # sys.exit(app.processEvents())
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
