from __future__ import annotations

from collections import defaultdict
from typing import Any

from PyQt6 import QtCore, QtGui, QtWidgets


class FlattenModel(QtCore.QIdentityProxyModel):
    def __init__(
        self, row_depth: int = 0, parent: QtCore.QObject | None = None
    ) -> None:
        super().__init__(parent)
        # the row depth determines how many rows we show in the flattened view
        # for example, if row_depth=0, we revert to the original model,
        self._row_depth = row_depth
        self._rows: list[QtCore.QModelIndex] = []
        # Store which rows are expandable and their children
        self._expandable_rows: dict[int, list[list[tuple[int, int]]]] = {}

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = QtCore.Qt.ItemDataRole.DisplayRole,
    ) -> Any:
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
        else:
            # For a parent row, return number of children if expandable
            parent_row = parent.row()
            if parent_row in self._expandable_rows:
                return len(self._expandable_rows[parent_row])
            return 0

    def columnCount(self, parent: QtCore.QModelIndex | None = None) -> int:
        if parent is None:
            parent = QtCore.QModelIndex()
        # In the flattened view with hierarchical expansion,
        # we need enough columns to show the deepest child data
        if self._row_depth <= 0:
            return super().columnCount(parent)

        # Calculate the maximum depth needed including children
        max_child_depth = self._max_depth
        for children_paths in self._expandable_rows.values():
            for path in children_paths:
                max_child_depth = max(max_child_depth, len(path) - 1)

        return max_child_depth + 1

    def set_row_depth(self, row_depth: int) -> None:
        self._row_depth = row_depth
        self._rebuild()

    def setSourceModel(self, source_model: QtCore.QAbstractItemModel | None) -> None:
        super().setSourceModel(source_model)
        if source_model:
            source_model.dataChanged.connect(self._rebuild)
        self._rebuild()

    def _rebuild(self) -> None:
        self.beginResetModel()
        self._max_depth = 0
        # one entry per proxy row
        self._row_paths: list[list[tuple[int, int]]] = []
        # mapping of depth -> (num_rows, num_columns)
        self._num_leafs_at_depth = defaultdict[int, int](int)
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
        self._num_leafs_at_depth[depth] += rows
        self._max_depth = max(self._max_depth, depth)

        for r in range(rows):
            child = model.index(r, 0, parent)  # tree is in column 0
            pair_path = [*stack, (r, 0)]

            if depth == self._row_depth:
                # Add the row at the target depth
                row_index = len(self._row_paths)
                self._row_paths.append(pair_path)

                # If this row has children, store them for potential expansion
                if model.hasChildren(child):
                    children = []
                    child_rows = model.rowCount(child)
                    for child_r in range(child_rows):
                        child_path = [*pair_path, (child_r, 0)]
                        children.append(child_path)
                    self._expandable_rows[row_index] = children
            else:
                self._collect_model_shape(model, child, depth + 1, pair_path)

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
            if column < 0 or column > self._max_depth:
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

    def parent(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:
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
            return self.createIndex(parent_row, 0, 0)  # Parent is always top-level

    def mapToSource(self, proxy_index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        """Map from the flattened view back to the source model."""
        if self._row_depth <= 0 or not (src_model := self.sourceModel()):
            return super().mapToSource(proxy_index)

        if not proxy_index.isValid():
            return QtCore.QModelIndex()

        row, col = proxy_index.row(), proxy_index.column()
        internal_ptr = proxy_index.internalId()

        if internal_ptr == 0:
            # Top-level row
            if row >= len(self._row_paths):
                return QtCore.QModelIndex()
            path = self._row_paths[row]
        else:
            # Child row
            parent_row = internal_ptr - 1
            if parent_row not in self._expandable_rows:
                return QtCore.QModelIndex()
            children = self._expandable_rows[parent_row]
            if row >= len(children):
                return QtCore.QModelIndex()
            path = children[row]

        if col >= len(path):  # beyond recorded depth
            return QtCore.QModelIndex()

        src = QtCore.QModelIndex()
        for r, c in path[: col + 1]:
            src = src_model.index(r, c, src)

        return src

    def data(
        self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole
    ) -> Any:
        """Return data for the given index and role."""
        if self._row_depth <= 0:
            return super().data(index, role)

        if not index.isValid() or not (src_model := self.sourceModel()):
            return None

        row, col = index.row(), index.column()
        internal_ptr = index.internalId()

        if internal_ptr == 0:
            # Top-level row
            if row >= len(self._row_paths):
                return None
            path = self._row_paths[row]
        else:
            # Child row
            parent_row = internal_ptr - 1
            if parent_row not in self._expandable_rows:
                return None
            children = self._expandable_rows[parent_row]
            if row >= len(children):
                return None
            path = children[row]

        if col >= len(path):
            return None

        # Navigate to the source index for this column
        src = QtCore.QModelIndex()
        for _, (r, c) in enumerate(path[: col + 1]):
            src = src_model.index(r, c, src)

        return src_model.data(src, role) if src.isValid() else None

    def hasChildren(self, parent: QtCore.QModelIndex | None = None) -> bool:
        """Return whether the given index has children."""
        if parent is None:
            parent = QtCore.QModelIndex()

        if self._row_depth <= 0:
            return super().hasChildren(parent)

        if not parent.isValid():
            return self.rowCount() > 0

        # Check if this is a top-level row that's expandable
        if parent.internalId() == 0:
            parent_row = parent.row()
            return parent_row in self._expandable_rows

        # Child rows don't have children in this implementation
        return False


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
        tree2.setModel(self.proxy)
        tree1.expandAll()

        # depth selector
        depth_selector = QtWidgets.QComboBox()
        depth_selector.addItems(
            [
                "Rows = level A (depth 0)",
                "Rows = level B (depth 1)",
                "Rows = level C (depth 2)",
            ]
        )
        depth_selector.setCurrentIndex(1)

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
    print("Testing hierarchical expansion at row_depth=1:")
    win.proxy.set_row_depth(1)
    print(f"Row count (top-level): {win.proxy.rowCount()}")

    # Print top-level rows
    for r in range(win.proxy.rowCount()):
        row_data = []
        for c in range(win.proxy.columnCount()):
            idx = win.proxy.index(r, c)
            data = win.proxy.data(idx)
            row_data.append(str(data) if data else "None")
        has_children = win.proxy.hasChildren(win.proxy.index(r, 0))
        print(f"  Row {r}: {row_data} (has children: {has_children})")

        # If this row has children, print them too
        if has_children:
            parent_idx = win.proxy.index(r, 0)
            child_count = win.proxy.rowCount(parent_idx)
            print(f"    Children ({child_count}):")
            for child_r in range(child_count):
                child_data = []
                for c in range(win.proxy.columnCount()):
                    child_idx = win.proxy.index(child_r, c, parent_idx)
                    data = win.proxy.data(child_idx)
                    child_data.append(str(data) if data else "None")
                print(f"      Child {child_r}: {child_data}")

                # Test bounds checking: try to get parent of child
                child_parent = win.proxy.parent(child_idx)
                if child_parent.isValid():
                    print(f"        Child parent row: {child_parent.row()}")

    print("\nStress testing bounds checking:")
    # Try to create invalid indexes and see if they handle gracefully
    invalid_tests = [
        (999, 0, QtCore.QModelIndex()),  # Invalid top-level row
        (0, 999, QtCore.QModelIndex()),  # Invalid column
        (-1, 0, QtCore.QModelIndex()),  # Negative row
        (0, -1, QtCore.QModelIndex()),  # Negative column
    ]

    for row, col, parent in invalid_tests:
        index = win.proxy.index(row, col, parent)
        print(f"    index({row}, {col}): valid={index.isValid()}")
        if index.isValid():
            # Try to get parent, which might trigger the overflow
            try:
                parent_index = win.proxy.parent(index)
                print(f"      parent: valid={parent_index.isValid()}")
            except Exception as e:
                print(f"      parent error: {e}")

    # Try to trigger the overflow with corrupted internal pointers
    print("\nTesting with potentially corrupted indexes:")
    try:
        # Create an index with a very large internal pointer manually
        # This simulates what might happen in edge cases
        for large_id in [999999, 2**31, 2**63 - 1]:
            try:
                fake_index = win.proxy.createIndex(0, 0, large_id)
                print(f"    Created index with internalId={large_id}")
                parent_index = win.proxy.parent(fake_index)
                print(f"      Parent: valid={parent_index.isValid()}")
            except Exception as e:
                print(f"      Error with internalId={large_id}: {e}")
    except Exception as e:
        print(f"    Exception in corruption test: {e}")

    # Expand all in the tree view to show hierarchical structure
    win.tree2.expandAll()

    win.grab().save("flatten_proxy_demo.png", "PNG")
    sys.exit(app.exec())
    # sys.exit(app.processEvents())


if __name__ == "__main__":
    main()
