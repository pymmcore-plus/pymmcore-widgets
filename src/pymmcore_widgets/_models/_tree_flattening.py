from __future__ import annotations

from collections import defaultdict
from typing import Any

from qtpy.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
)


class _Token:
    """Unique, stable pointer stored in each QModelIndex."""

    __slots__ = ("is_child", "top_row")

    def __init__(self, top_row: int, is_child: bool = False) -> None:
        self.top_row = top_row
        self.is_child = is_child


class TreeFlatteningProxy(QSortFilterProxyModel):
    """A proxy model that flattens a tree model into a table view with expandable rows.

    This model allows you to specify a row depth, which determines how many rows are
    shown in the flattened view. For example, if row_depth=0, it reverts to the original
    model, while row_depth=1 shows the first level of children, and row_depth=2 shows
    the second level of children. The model supports expandable rows, allowing users to
    expand and collapse child rows based on the specified depth.
    """

    def __init__(self, parent: QObject | None = None, row_depth: int = 0) -> None:
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

        # stable pointers reused by createIndex
        self._top_tokens: list[_Token] = []
        self._child_tokens: dict[tuple[int, int], _Token] = {}

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

    # def rowCount(self, parent: QModelIndex | None = None) -> int:
    #     """Return the number of rows under *parent* in the flattened view."""
    #     if parent is None:
    #         parent = QModelIndex()
    #     if self._row_depth <= 0:
    #         return int(super().rowCount(parent))

    #     if not parent.isValid():
    #         # root in proxy - every top-level row represents one path we stored
    #         return len(self._row_paths)

    #     # Top-level rows have an **even** internalId; they may expose children.
    #     if (parent.internalId() & 1) == 0:
    #         children = self._expandable_rows.get(parent.row())
    #         return len(children) if children is not None else 0

    #     # Child rows (odd internalId) never have further children in this proxy
    #     return 0

    def hasChildren(self, parent: QModelIndex | None = None) -> bool:
        return self.rowCount(parent) > 0

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
        """Set the source model and rebuild whenever the source structure changes."""
        # Disconnect from the old model (if any)
        old_model = self.sourceModel()
        if old_model is not None:
            try:
                old_model.dataChanged.disconnect(self._rebuild)
                old_model.rowsInserted.disconnect(self._rebuild)
                old_model.rowsRemoved.disconnect(self._rebuild)
                old_model.columnsInserted.disconnect(self._rebuild)
                old_model.columnsRemoved.disconnect(self._rebuild)
                old_model.layoutChanged.disconnect(self._rebuild)
                old_model.modelReset.disconnect(self._rebuild)
            except (TypeError, RuntimeError):
                # Signals may already be disconnected or the model deleted
                pass

        super().setSourceModel(source_model)

        # Connect to the new model (if provided)
        if source_model is not None:
            # All of these signals indicate that the structure of the source
            # model has changed in a way that could invalidate our cached
            # row/column paths - so trigger a rebuild.
            for sig in (
                source_model.dataChanged,
                source_model.rowsInserted,
                source_model.rowsRemoved,
                source_model.columnsInserted,
                source_model.columnsRemoved,
                source_model.layoutChanged,
                source_model.modelReset,
            ):
                # We ignore all positional arguments from the signal.
                sig.connect(lambda *_, **__: self._rebuild())

        # Build initial flattened representation
        self._rebuild()

    # ------------------------------------------------------------------
    # Index <-> Parent helpers
    #
    #  * top-level   internalId = row << 1      (always even)
    #  * child rows  internalId = (row << 1)|1  (always odd)
    # ------------------------------------------------------------------

    # def index(
    #     self,
    #     row: int,
    #     column: int,
    #     parent: QModelIndex | None = None,
    # ) -> QModelIndex:
    #     """Return proxy QModelIndex for (row, column, parent)."""
    #     if parent is None:
    #         parent = QModelIndex()
    #     if self._row_depth <= 0:
    #         return super().index(row, column, parent)

    #     # ---------------- root → top-level rows ----------------
    #     if not parent.isValid():
    #         if (
    #             row < 0
    #             or row >= len(self._row_paths)
    #             or column < 0
    #             or column >= self.columnCount()
    #         ):
    #             return QModelIndex()
    #         return self.createIndex(row, column, row << 1)  # even id

    #     # ---------------- top-level → child rows ---------------
    #     if (parent.internalId() & 1) == 0:  # only top-level may have children
    #         top_row = parent.row()
    #         children = self._expandable_rows.get(top_row)
    #         if children is None:
    #             return QModelIndex()
    #         if (
    #             row < 0
    #             or row >= len(children)
    #             or column < 0
    #             or column >= self.columnCount()
    #         ):
    #             return QModelIndex()
    #         return self.createIndex(row, column, (top_row << 1) | 1)  # odd id

    #     # children have no further descendants
    #     return QModelIndex()

    # def parent(self, index: QModelIndex) -> QModelIndex:
    #     """Return the parent of *index* in the flattened hierarchy."""
    #     if self._row_depth <= 0:
    #         return super().parent(index)

    #     if not index.isValid():
    #         return QModelIndex()

    #     internal_id = index.internalId()

    #     # child-less top-level rows
    #     if (internal_id & 1) == 0:
    #         return QModelIndex()  # root

    #     # child → parent is encoded in high bits
    #     parent_row = internal_id >> 1
    #     if 0 <= parent_row < len(self._row_paths):
    #         return self.createIndex(parent_row, 0, parent_row << 1)

    #     return QModelIndex()

    def mapToSource(self, proxy_index: QModelIndex) -> QModelIndex:
        """Translate a proxy index back to the source model."""
        if self._row_depth <= 0 or not (src_model := self.sourceModel()):
            return super().mapToSource(proxy_index)

        if not proxy_index.isValid():
            return QModelIndex()

        row, col = proxy_index.row(), proxy_index.column()

        tok = proxy_index.internalPointer()
        is_child = isinstance(tok, _Token) and tok.is_child

        if not is_child:
            # ---- top-level proxy row ----
            if row >= len(self._row_paths):
                return QModelIndex()

            path = self._row_paths[row]
            if col >= len(path):  # beyond recorded depth
                return QModelIndex()

            src = QModelIndex()
            for r, c in path[: col + 1]:
                src = src_model.index(r, c, src)
            return src

        # ---- child proxy row ----
        parent_row = tok.top_row
        children = self._expandable_rows.get(parent_row)
        if children is None or row >= len(children):
            return QModelIndex()

        path = children[row]
        if col == 0:
            return QModelIndex()  # intentionally empty - indentation column
        if col != self._row_depth:
            return QModelIndex()  # other columns unused for child rows

        src = QModelIndex()
        for r, c in path:
            src = src_model.index(r, c, src)
        return src

    def mapFromSource(self, source_index: QModelIndex) -> QModelIndex:
        """Translate a source index to the corresponding proxy index."""
        if self._row_depth <= 0 or not self.sourceModel():
            return super().mapFromSource(source_index)

        if not source_index.isValid():
            return QModelIndex()

        # Build path root→…→source_index
        path: list[tuple[int, int]] = []
        cur = source_index
        while cur.isValid():
            path.append((cur.row(), cur.column()))
            cur = cur.parent()
        path.reverse()

        # We flattened the tree by collecting *row_depth*-deep paths into
        # `self._row_paths`.  Each proxy row therefore has:
        #
        #   column 0  → node at depth 0   (device)
        #   column 1  → node at depth 1   (property)   when row_depth == 1
        #
        # For a given *source* index we need to decide which proxy column
        # represents it.
        for proxy_row, row_path in enumerate(self._row_paths):
            if path == row_path:  # exact match → deepest column
                column = len(path) - 1  # row_depth
                return self.createIndex(proxy_row, column, self._top_tokens[proxy_row])

            # Is the source index the ancestor at depth-0 of this row?
            # (e.g. device row when the proxy row represents a property)
            if path == row_path[: len(path)]:
                column = len(path) - 1  # 0 for device
                return self.createIndex(proxy_row, column, self._top_tokens[proxy_row])

        return QModelIndex()

    def _rebuild(self) -> None:
        self.beginResetModel()
        self._max_depth = 0
        self._top_tokens.clear()
        self._child_tokens.clear()
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

    # def sort(
    #     self,
    #     column: int,
    #     order: Qt.SortOrder = Qt.SortOrder.AscendingOrder,
    # ) -> None:
    #     """Sort the proxy model by the specified column."""
    #     if self._row_depth <= 0:
    #         return super().sort(column, order)  # type: ignore[no-any-return]

    #     if column < 0 or column >= self.columnCount():
    #         return  # Invalid column

    #     # Emit layoutAboutToBeChanged signal
    #     self.layoutAboutToBeChanged.emit()

    #     # Sort our _row_paths based on the data in the specified column
    #     def get_sort_key(row_index: int) -> str:
    #         """Get the sort key for a row at the given index."""
    #         proxy_idx = self.index(row_index, column)
    #         data = self.data(proxy_idx, Qt.ItemDataRole.DisplayRole)
    #         return str(data) if data is not None else ""

    #     # Create list of (original_index, sort_key) pairs
    #     indexed_rows = [(i, get_sort_key(i)) for i in range(len(self._row_paths))]

    #     # Sort by the sort key
    #     reverse_order = order == Qt.SortOrder.DescendingOrder
    #     indexed_rows.sort(key=lambda x: x[1], reverse=reverse_order)

    #     # Reorder _row_paths and _expandable_rows based on sorted order
    #     old_row_paths = self._row_paths.copy()
    #     old_expandable_rows = self._expandable_rows.copy()

    #     self._row_paths = []
    #     self._expandable_rows = {}

    #     for new_index, (old_index, _) in enumerate(indexed_rows):
    #         # Copy the row path
    #         self._row_paths.append(old_row_paths[old_index])

    #         # Copy expandable rows mapping with new index
    #         if old_index in old_expandable_rows:
    #             self._expandable_rows[new_index] = old_expandable_rows[old_index]

    #     # Emit layoutChanged signal
    #     self.layoutChanged.emit()
    # ------------------------------------------------------------------
    # Index / Parent helpers - we use _Token pointers, never integers
    # ------------------------------------------------------------------

    def index(
        self, row: int, column: int, parent: QModelIndex | None = None
    ) -> QModelIndex:
        if parent is None:
            parent = QModelIndex()
        if self._row_depth <= 0:
            return super().index(row, column, parent)

        # ---------- root → top-level ----------
        if not parent.isValid():
            if not (0 <= row < len(self._row_paths)) or not (
                0 <= column < self.columnCount()
            ):
                return QModelIndex()
            # reuse token
            while row >= len(self._top_tokens):
                self._top_tokens.append(_Token(len(self._top_tokens)))
            return self.createIndex(row, column, self._top_tokens[row])

        # ---------- top-level → child ----------
        p_tok = parent.internalPointer()
        if isinstance(p_tok, _Token) and not p_tok.is_child:
            top_row = p_tok.top_row
            children = self._expandable_rows.get(top_row)
            if (
                children is None
                or not (0 <= row < len(children))
                or not (0 <= column < self.columnCount())
            ):
                return QModelIndex()
            key = (top_row, row)
            token = self._child_tokens.get(key)
            if token is None:
                token = _Token(top_row, True)
                self._child_tokens[key] = token
            return self.createIndex(row, column, token)

        return QModelIndex()  # a child has no grandchildren

    def parent(self, index: QModelIndex) -> QModelIndex:
        if self._row_depth <= 0:
            return super().parent(index)
        if not index.isValid():
            return QModelIndex()

        tok = index.internalPointer()
        if not isinstance(tok, _Token) or not tok.is_child:
            return QModelIndex()  # top-level rows → root

        top_row = tok.top_row
        if 0 <= top_row < len(self._top_tokens):
            return self.createIndex(top_row, 0, self._top_tokens[top_row])
        return QModelIndex()

    def sibling(self, row: int, column: int, index: QModelIndex) -> QModelIndex:
        """Return a sibling index for the given row and column."""
        if not index.isValid():
            return QModelIndex()

        parent_index = self.parent(index)
        return self.index(row, column, parent_index)

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is None:
            parent = QModelIndex()
        if self._row_depth <= 0:
            return int(super().rowCount(parent))

        if not parent.isValid():
            return len(self._row_paths)

        tok = parent.internalPointer()
        if isinstance(tok, _Token) and not tok.is_child:
            ch = self._expandable_rows.get(tok.top_row)
            return len(ch) if ch else 0
        return 0
