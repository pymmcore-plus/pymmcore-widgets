from __future__ import annotations

import sys
from typing import NamedTuple

from qtpy import QtCore, QtWidgets
from qtpy.QtCore import QAbstractProxyModel, QModelIndex, QPersistentModelIndex, Qt
from qtpy.QtGui import QStandardItem, QStandardItemModel
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


class RowInfo(NamedTuple):
    leaf: QPersistentModelIndex
    ancestors: list[QPersistentModelIndex]


class FlattenProxyModel(QAbstractProxyModel):
    def __init__(self, level: int = 0, parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self._level = level
        self._rows: list[RowInfo] = []
        self._src2row: dict[QPersistentModelIndex, int] = {}
        self._mixed = False  # Whether to show mixed hierarchy
        self._child_cache: dict[
            QPersistentModelIndex, QPersistentModelIndex
        ] = {}  # Cache for child indices

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------
    def _validate(self, idx: QModelIndex) -> None:
        """Verify that every index we emit stores either None or a QPersistentModelIndex."""
        if not idx.isValid():
            return
        ip = idx.internalPointer()
        if ip is not None and not isinstance(ip, QPersistentModelIndex):
            raise RuntimeError(f"Bad internalPointer detected: {ip!r}")

    def _ci(self, row: int, col: int, ptr) -> QModelIndex:
        """CreateIndex + validation wrapper."""
        idx = self.createIndex(row, col, ptr)
        self._validate(idx)
        return idx

    def setLevel(self, level: int):
        self._level = level
        self._rebuild()

    def setMixed(self, mixed: bool):
        self._mixed = mixed
        self._rebuild()

    def _rebuild(self):
        self.beginResetModel()
        self._rows.clear()
        self._src2row.clear()
        self._child_cache.clear()
        self._child_cache.clear()

        if not self.sourceModel():
            self.endResetModel()
            return

        if self._level < 0:
            # Pass-through mode
            self.endResetModel()
            return

        # Build flattened rows
        self._traverse(QModelIndex(), [])
        self.endResetModel()

    def _traverse(self, parent: QModelIndex, ancestors: list[QPersistentModelIndex]):
        for r in range(self.sourceModel().rowCount(parent)):
            child = self.sourceModel().index(r, 0, parent)
            child_ancestors = [*ancestors, QPersistentModelIndex(child)]

            if len(child_ancestors) - 1 == self._level:
                # This is a leaf at the desired level
                row_info = RowInfo(QPersistentModelIndex(child), child_ancestors)
                self._src2row[QPersistentModelIndex(child)] = len(self._rows)
                self._rows.append(row_info)
            elif len(child_ancestors) - 1 < self._level:
                # Keep going deeper
                self._traverse(child, child_ancestors)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if not self.sourceModel():
            return 0

        if self._level < 0:
            # Pass-through mode
            return self.sourceModel().rowCount(self.mapToSource(parent))

        if not parent.isValid():
            # Top-level: return number of flattened rows
            return len(self._rows)

        # Mixed hierarchy: children of flattened rows
        if self._mixed and not parent.internalPointer():
            # Children of a flattened row
            try:
                rowinfo = self._rows[parent.row()]
                src_parent = QModelIndex(rowinfo.leaf)
                return self.sourceModel().rowCount(src_parent)
            except:
                return 0

        # Grandchildren or deeper
        # New: if parent.internalPointer() is a QPersistentModelIndex
        if self._mixed and isinstance(parent.internalPointer(), QPersistentModelIndex):
            src_parent_persistent = parent.internalPointer()
            if src_parent_persistent.isValid():
                src_parent = QModelIndex(src_parent_persistent)
                return self.sourceModel().rowCount(src_parent)

        return 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if not self.sourceModel():
            return 0
        if self._level < 0:
            # Pass-through mode
            return self.sourceModel().columnCount()
        # In flattened mode, show columns for each level in the hierarchy
        return self._level + 1

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        if not self.sourceModel():
            return False

        if self._level < 0:
            # Pass-through mode
            src_index = self.mapToSource(parent)
            return self.sourceModel().hasChildren(src_index)

        if not parent.isValid():
            # Top-level always has children (the flattened rows)
            return len(self._rows) > 0

        # Mixed hierarchy: check if flattened rows have children
        if self._mixed and not parent.internalPointer():
            try:
                if parent.row() < len(self._rows):
                    rowinfo = self._rows[parent.row()]
                    # Recreate QModelIndex from QPersistentModelIndex using its data
                    if rowinfo.leaf.isValid():
                        # Get the parent of the leaf to recreate the hierarchy
                        persistent_parent = (
                            rowinfo.leaf.parent()
                            if rowinfo.leaf.parent().isValid()
                            else QModelIndex()
                        )
                        src_index = self.sourceModel().index(
                            rowinfo.leaf.row(), rowinfo.leaf.column(), persistent_parent
                        )
                        return self.sourceModel().hasChildren(src_index)
            except Exception:
                pass
            return False

        # Grandchildren or deeper
        # New: handle QPersistentModelIndex stored in internalPointer
        if self._mixed and isinstance(parent.internalPointer(), QPersistentModelIndex):
            src_parent_persistent = parent.internalPointer()
            if src_parent_persistent.isValid():
                src_parent = QModelIndex(src_parent_persistent)
                return self.sourceModel().hasChildren(src_parent)
            return False

        return False

    def index(
        self, row: int, col: int, parent: QModelIndex = QModelIndex()
    ) -> QModelIndex:
        if row < 0 or col < 0:
            return QModelIndex()

        if not self.sourceModel():
            return QModelIndex()

        # Pass-through mode
        if self._level < 0:
            try:
                src_parent = self.mapToSource(parent)
                if not src_parent.isValid() and parent.isValid():
                    return QModelIndex()
                return self._ci(row, col, None)
            except Exception:
                return QModelIndex()

        # Top-level flattened row
        if not parent.isValid():
            if row >= len(self._rows) or col >= self.columnCount():
                return QModelIndex()
            return self._ci(row, col, None)

        # Mixed hierarchy disabled - no children
        if not self._mixed:
            return QModelIndex()

        # Mixed hierarchy: children of flattened rows
        if parent.internalPointer() is None:
            if parent.row() >= len(self._rows):
                return QModelIndex()
            rowinfo = self._rows[parent.row()]
            if not rowinfo.leaf.isValid():
                return QModelIndex()
            src_parent = rowinfo.leaf.model().index(
                rowinfo.leaf.row(),
                rowinfo.leaf.column(),
                QModelIndex(),
            )
            if col != 0:
                return QModelIndex()
            if row >= self.sourceModel().rowCount(src_parent):
                return QModelIndex()
            src_child = self.sourceModel().index(row, 0, src_parent)
            if not src_child.isValid():
                return QModelIndex()
            # Use the persistent source index directly as internal pointer
            persistent = QPersistentModelIndex(src_child)
            self._child_cache[persistent] = persistent
            return self._ci(row, col, persistent)

        # Grandchildren or deeper
        elif parent.internalPointer() is not None:
            # Use the persistent source index directly as internal pointer
            persistent = QPersistentModelIndex(
                self.sourceModel().index(row, 0, QModelIndex(parent.internalPointer()))
            )
            src_parent_persistent = parent.internalPointer()
            if (
                not isinstance(src_parent_persistent, QPersistentModelIndex)
                or not src_parent_persistent.isValid()
            ):
                return QModelIndex()
            src_parent = QModelIndex(src_parent_persistent)
            if col != 0:
                return QModelIndex()
            if row >= self.sourceModel().rowCount(src_parent):
                return QModelIndex()
            src_child = self.sourceModel().index(row, 0, src_parent)
            if not src_child.isValid():
                return QModelIndex()
            persistent = QPersistentModelIndex(src_child)
            self._child_cache[persistent] = persistent
            return self._ci(row, col, persistent)

        return QModelIndex()

    def parent(self, child: QModelIndex) -> QModelIndex:
        if not child.isValid() or self._level < 0:
            return QModelIndex()

        # If this is a top-level flattened row, it has no parent
        if child.internalPointer() is None:
            return QModelIndex()

        # If this is a mixed hierarchy child
        if self._mixed and isinstance(child.internalPointer(), QPersistentModelIndex):
            child_persistent = child.internalPointer()
            if not child_persistent.isValid():
                return QModelIndex()

            src_child = QModelIndex(child_persistent)
            src_parent = src_child.parent()

            psrc_parent = QPersistentModelIndex(src_parent)
            if psrc_parent in self._src2row:
                return self._ci(self._src2row[psrc_parent], 0, None)

            if src_parent.isValid():
                parent_persistent = QPersistentModelIndex(src_parent)
                self._child_cache[parent_persistent] = parent_persistent
                return self._ci(src_parent.row(), 0, parent_persistent)

            return QModelIndex()

        return QModelIndex()

    def mapToSource(self, proxy: QModelIndex) -> QModelIndex:
        if not proxy.isValid() or not self.sourceModel():
            return QModelIndex()

        if self._level < 0:
            # Pass-through mode
            try:
                return self.sourceModel().index(
                    proxy.row(), proxy.column(), QModelIndex()
                )
            except Exception:
                return QModelIndex()

        # Top-level flattened row showing hierarchical path
        if proxy.internalPointer() is None:
            if proxy.row() >= len(self._rows):
                return QModelIndex()
            row_info = self._rows[proxy.row()]
            # Return the ancestor at the requested column level
            if proxy.column() < len(row_info.ancestors):
                ancestor = row_info.ancestors[proxy.column()]
                if isinstance(ancestor, QPersistentModelIndex) and ancestor.isValid():
                    return QModelIndex(ancestor)
            return QModelIndex()

        # Mixed hierarchy child
        if self._mixed and isinstance(proxy.internalPointer(), QPersistentModelIndex):
            cached_persistent = proxy.internalPointer()
            if cached_persistent.isValid():
                return QModelIndex(cached_persistent)
            return QModelIndex()

        return QModelIndex()

    def mapFromSource(self, src: QModelIndex) -> QModelIndex:
        if not src.isValid() or not self.sourceModel():
            return QModelIndex()

        if self._level < 0:
            # Pass-through mode
            try:
                return self._ci(src.row(), src.column(), None)
            except:
                return QModelIndex()

        psrc = QPersistentModelIndex(src)

        # Check if this is a flattened row
        if (row := self._src2row.get(psrc)) is not None:
            return self.index(row, 0)

        # Check if this is in the ancestors of any flattened row
        for r, info in enumerate(self._rows):
            if psrc in info.ancestors:
                col = info.ancestors.index(psrc)
                return self.index(r, col)

        if self._mixed:
            psrc_child = QPersistentModelIndex(src)
            self._child_cache[psrc_child] = psrc_child
            return self._ci(src.row(), 0, psrc_child)

        return QModelIndex()

    def data(self, idx: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not idx.isValid() or not self.sourceModel():
            return None
        try:
            return self.sourceModel().data(self.mapToSource(idx), role)
        except:
            return None

    def headerData(
        self,
        section: int,
        orient: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if not self.sourceModel():
            return None

        if (
            orient == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and self._level >= 0
        ):
            if section == 0:
                return "A"
            elif section == 1:
                return "B"
            elif section == 2:
                return "C"
            elif section == 3:
                return "D"
            elif section == 4:
                return "E"
            else:
                return f"Level {section}"

        return self.sourceModel().headerData(section, orient, role)

    def setSourceModel(self, model):
        if self.sourceModel():
            try:
                self.sourceModel().modelReset.disconnect(self._rebuild)
            except:
                pass
        super().setSourceModel(model)
        if model:
            model.modelReset.connect(self._rebuild)
            self._rebuild()


# Demo window
class DemoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tree Flatten Demo")
        self.resize(1200, 600)

        # Create source model
        self.src_model = QStandardItemModel()
        self._populate_model()

        # Create proxy model
        self.flatten = FlattenProxyModel(level=3)
        self.flatten.setSourceModel(self.src_model)

        from qtpy.QtTest import QAbstractItemModelTester

        QAbstractItemModelTester(
            self.flatten,
            QAbstractItemModelTester.FailureReportingMode.Fatal,
            self,
        )

        # Create layout
        layout = QVBoxLayout(self)

        # Controls
        controls = QHBoxLayout()

        # Level selector
        controls.addWidget(QLabel("Flatten Level:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(
            ["Pass-through", "Level 0 - A", "Level 1 - B", "Level 2 - C", "Level 3 - D"]
        )
        self.level_combo.setCurrentIndex(4)  # Level 3 - D
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        controls.addWidget(self.level_combo)

        # Mixed hierarchy checkbox
        self.mixed_check = QtWidgets.QCheckBox("Mixed Hierarchy")
        self.mixed_check.setChecked(True)  # Try with True to test
        self.mixed_check.toggled.connect(self._on_mixed_changed)
        controls.addWidget(self.mixed_check)

        controls.addStretch()
        layout.addLayout(controls)

        # Views
        views_layout = QHBoxLayout()

        # Original view
        orig_view = QTreeView()
        orig_view.setModel(self.src_model)
        orig_view.expandAll()
        orig_view.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        views_layout.addWidget(orig_view)

        # Flattened view
        flat_view = QTreeView()
        flat_view.setModel(self.flatten)
        flat_view.expandAll()
        flat_view.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        flat_view.header().setStretchLastSection(True)
        views_layout.addWidget(flat_view)

        layout.addLayout(views_layout)

        # Set initial state
        self._on_level_changed(2)  # Level 2 - B
        self._on_mixed_changed(True)  # Try with mixed hierarchy

    def _populate_model(self):
        root = self.src_model.invisibleRootItem()
        d = 2
        for i in range(d):
            item_a = QStandardItem(f"A{i}")
            root.appendRow(item_a)
            for j in range(d):
                item_b = QStandardItem(f"B{j}")
                item_a.appendRow(item_b)
                for k in range(d):
                    item_c = QStandardItem(f"C{k}")
                    item_b.appendRow(item_c)
                    # for l in range(d):
                    #     item_d = QStandardItem(f"D{l}")
                    #     item_c.appendRow(item_d)
                    #     for m in range(d):
                    #         item_e = QStandardItem(f"E{m}")
                    #         item_d.appendRow(item_e)

    def _parse_level_from_combo(self, index: int) -> int:
        if index == 0:
            return -1  # Pass-through
        return index - 1

    def _on_level_changed(self, index: int):
        level = self._parse_level_from_combo(index)
        self.flatten.setLevel(level)

    def _on_mixed_changed(self, checked: bool):
        self.flatten.setMixed(checked)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DemoWindow()

    window.show()
    # sys.exit(app.exec())
    app.processEvents()
