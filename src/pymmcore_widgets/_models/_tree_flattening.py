from __future__ import annotations

from collections import defaultdict
from typing import Any

from qtpy.QtCore import (
    QAbstractItemModel,
    QIdentityProxyModel,
    QModelIndex,
    QObject,
    Qt,
)


class TreeFlatteningProxy(QIdentityProxyModel):
    """A proxy model that flattens a tree model into a table view with expandable rows.

    This model allows you to specify a row depth, which determines how many rows are
    shown in the flattened view. For example, if row_depth=0, it reverts to the original
    model, while row_depth=1 shows the first level of children, and row_depth=2 shows
    the second level of children. The model supports expandable rows, allowing users to
    expand and collapse child rows based on the specified depth.
    """

    def __init__(self, row_depth: int = 0, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # the row depth determines how many rows we show in the flattened view
        # for example, if row_depth=0, we revert to the original model,
        self._row_depth = row_depth

        # Store which rows are expandable and their children
        self._expandable_rows: dict[int, list[list[tuple[int, int]]]] = {}
        # mapping of depth -> (num_rows, num_columns)
        self._num_leaves_at_depth = defaultdict[int, int](int)
        # max depth of the tree model
        self._max_depth = 0
        # one entry per proxy row
        self._row_paths: list[list[tuple[int, int]]] = []

    def set_row_depth(self, row_depth: int) -> None:
        """Set the row depth for the flattened view."""
        self._row_depth = row_depth
        self._rebuild()

    # ------------- QAbstractItemModel interface methods -------------

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Return the header data for the given section and orientation."""
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return f"Level {section}"  # Level 0 = root, Level N = leaf
        return super().headerData(section, orientation, role)

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        """Return the number of rows under the given parent."""
        if parent is None:
            parent = QModelIndex()
        if self._row_depth <= 0:
            return int(super().rowCount(parent))

        if not parent.isValid():
            # Top-level: return number of primary flattened rows
            return len(self._row_paths)

        # For a parent row, return number of children if expandable
        if parent.internalId() == 0:  # Top-level row
            parent_row = parent.row()
            if parent_row in self._expandable_rows:
                return len(self._expandable_rows[parent_row])
        return 0

    def hasChildren(self, parent: QModelIndex | None = None) -> bool:
        """Return whether the given index has children."""
        return bool(self.rowCount(parent))

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        """Return the number of columns for the given parent."""
        if parent is None:
            parent = QModelIndex()
        if self._row_depth <= 0:
            return int(super().columnCount(parent))

        # For flattened view, show columns up to row_depth + 1
        # This makes row_depth=1 show 2 columns, row_depth=2 show 3 columns, etc.
        return self._row_depth + 1

    def setSourceModel(self, source_model: QAbstractItemModel | None) -> None:
        """Set the source model and rebuild the flattened view."""
        super().setSourceModel(source_model)
        if source_model:
            source_model.dataChanged.connect(self._rebuild)
        self._rebuild()

    def index(
        self,
        row: int,
        column: int,
        parent: QModelIndex | None = None,
    ) -> QModelIndex:
        """Returns the index of the item specified by (row, column, parent)."""
        if parent is None:
            parent = QModelIndex()
        if self._row_depth <= 0:
            return super().index(row, column, parent)

        if not parent.isValid():
            # Top-level rows (the primary flattened rows)
            if row < 0 or row >= len(self._row_paths):
                return QModelIndex()
            if column < 0 or column >= self.columnCount():
                return QModelIndex()
            return self.createIndex(row, column, 0)  # 0 indicates top-level
        else:
            # Child rows (expanded children of a parent row)
            parent_row = parent.row()
            if parent_row in self._expandable_rows:
                children = self._expandable_rows[parent_row]
                if row < 0 or row >= len(children):
                    return QModelIndex()
                # For child rows, check against the child path length, not _max_depth
                child_path = children[row]
                max_child_col = len(child_path) - 1
                if column < 0 or column > max_child_col:
                    return QModelIndex()
                # Add bounds checking for parent_row to prevent overflow
                if parent_row < 0 or parent_row >= len(self._row_paths):
                    return QModelIndex()
                # Use parent_row + 1 as internal pointer to identify this is a child
                return self.createIndex(row, column, parent_row + 1)
            return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        """Returns the parent of the given child index."""
        if self._row_depth <= 0:
            return super().parent(index)

        if not index.isValid():
            return QModelIndex()

        internal_ptr = index.internalId()
        if internal_ptr == 0:
            # This is a top-level row, so no parent
            return QModelIndex()
        else:
            # This is a child row, parent is at internal_ptr - 1
            parent_row = internal_ptr - 1
            # Add bounds checking to prevent overflow
            if parent_row < 0 or parent_row >= len(self._row_paths):
                # Invalid parent row, return invalid index
                return QModelIndex()
            # Return parent at column 0 for tree structure
            return self.createIndex(parent_row, 0, 0)

    def mapToSource(self, proxy_index: QModelIndex) -> QModelIndex:
        """Map from the flattened view back to the source model."""
        if self._row_depth <= 0 or not (src_model := self.sourceModel()):
            return super().mapToSource(proxy_index)

        if not proxy_index.isValid():
            return QModelIndex()

        row, col = proxy_index.row(), proxy_index.column()
        internal_ptr = proxy_index.internalId()

        if internal_ptr == 0:
            # Top-level row: navigate to the column depth requested
            if row >= len(self._row_paths):
                return QModelIndex()
            path = self._row_paths[row]

            if col >= len(path):  # beyond recorded depth
                return QModelIndex()

            src = QModelIndex()
            for r, c in path[: col + 1]:
                src = src_model.index(r, c, src)
            return src
        else:
            # Child row: these are the deeper children (C-level nodes)
            parent_row = internal_ptr - 1
            if parent_row not in self._expandable_rows:
                return QModelIndex()
            children = self._expandable_rows[parent_row]
            if row >= len(children):
                return QModelIndex()
            path = children[row]

            # For children, we have different behavior per column:
            if col == 0:
                # Column 0: Don't show anything for child rows (they should be indented)
                return QModelIndex()
            elif col == self._row_depth:
                # Target depth column: show the full child data (navigate the full path)
                src = QModelIndex()
                for r, c in path:
                    src = src_model.index(r, c, src)
                return src
            else:
                # Other columns: no data
                return QModelIndex()

    def mapFromSource(self, source_index: QModelIndex) -> QModelIndex:
        """Map from source model back to proxy model."""
        if self._row_depth <= 0 or not (self.sourceModel()):
            return super().mapFromSource(source_index)

        if not source_index.isValid():
            return QModelIndex()

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

        return QModelIndex()

    def _rebuild(self) -> None:
        self.beginResetModel()
        self._max_depth = 0
        # one entry per proxy row
        self._row_paths = []
        # mapping of depth -> (num_rows, num_columns)
        self._num_leaves_at_depth = defaultdict[int, int](int)
        self._expandable_rows = {}
        if src := self.sourceModel():
            self._collect_model_shape(src)
        self.endResetModel()

    def _collect_model_shape(
        self,
        model: QAbstractItemModel,
        parent: QModelIndex | None = None,
        depth: int = 0,
        stack: list[tuple[int, int]] | None = None,
    ) -> None:
        if parent is None:
            parent = QModelIndex()
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

    def sort(
        self,
        column: int,
        order: Qt.SortOrder = Qt.SortOrder.AscendingOrder,
    ) -> None:
        """Sort the proxy model by the specified column."""
        if self._row_depth <= 0:
            return super().sort(column, order)  # type: ignore[no-any-return]

        if column < 0 or column >= self.columnCount():
            return  # Invalid column

        # Emit layoutAboutToBeChanged signal
        self.layoutAboutToBeChanged.emit()

        # Sort our _row_paths based on the data in the specified column
        def get_sort_key(row_index: int) -> str:
            """Get the sort key for a row at the given index."""
            proxy_idx = self.index(row_index, column)
            data = self.data(proxy_idx, Qt.ItemDataRole.DisplayRole)
            return str(data) if data is not None else ""

        # Create list of (original_index, sort_key) pairs
        indexed_rows = [(i, get_sort_key(i)) for i in range(len(self._row_paths))]

        # Sort by the sort key
        reverse_order = order == Qt.SortOrder.DescendingOrder
        indexed_rows.sort(key=lambda x: x[1], reverse=reverse_order)

        # Reorder _row_paths and _expandable_rows based on sorted order
        old_row_paths = self._row_paths.copy()
        old_expandable_rows = self._expandable_rows.copy()

        self._row_paths = []
        self._expandable_rows = {}

        for new_index, (old_index, _) in enumerate(indexed_rows):
            # Copy the row path
            self._row_paths.append(old_row_paths[old_index])

            # Copy expandable rows mapping with new index
            if old_index in old_expandable_rows:
                self._expandable_rows[new_index] = old_expandable_rows[old_index]

        # Emit layoutChanged signal
        self.layoutChanged.emit()
