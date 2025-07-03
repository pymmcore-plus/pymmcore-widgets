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
        self._child_cache: dict[int, QPersistentModelIndex] = {}  # Cache for child indices

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
        if self._mixed and parent.internalPointer():
            try:
                parent_id = parent.internalPointer()
                if isinstance(parent_id, int) and parent_id in self._child_cache:
                    src_parent_persistent = self._child_cache[parent_id]
                    if src_parent_persistent.isValid():
                        # Create new QModelIndex from QPersistentModelIndex
                        src_parent = self.sourceModel().index(
                            src_parent_persistent.row(),
                            src_parent_persistent.column(),
                            QModelIndex()  # Simplified for now
                        )
                        return self.sourceModel().rowCount(src_parent)
            except:
                pass
            return 0

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
                        persistent_parent = rowinfo.leaf.parent() if rowinfo.leaf.parent().isValid() else QModelIndex()
                        src_index = self.sourceModel().index(
                            rowinfo.leaf.row(),
                            rowinfo.leaf.column(),
                            persistent_parent
                        )
                        return self.sourceModel().hasChildren(src_index)
            except Exception:
                pass
            return False

        # Grandchildren or deeper
        if self._mixed and parent.internalPointer():
            try:
                parent_id = parent.internalPointer()
                if isinstance(parent_id, int) and parent_id in self._child_cache:
                    src_parent_persistent = self._child_cache[parent_id]
                    if src_parent_persistent.isValid():
                        # Create new QModelIndex from QPersistentModelIndex
                        src_parent = self.sourceModel().index(
                            src_parent_persistent.row(),
                            src_parent_persistent.column(),
                            QModelIndex()  # Simplified for now
                        )
                        return self.sourceModel().hasChildren(src_parent)
            except:
                pass
            return False

        return False

    def index(
        self, row: int, col: int, parent: QModelIndex = QModelIndex()
    ) -> QModelIndex:
        # print(f"index(row={row}, col={col}, parent={parent}, parent.internalPointer={parent.internalPointer() if parent.isValid() else None})")
        if row < 0 or col < 0:
            # print("  index: negative row/col")
            return QModelIndex()

        if not self.sourceModel():
            # print("  index: no sourceModel")
            return QModelIndex()

        # Pass-through mode
        if self._level < 0:
            try:
                src_parent = self.mapToSource(parent)
                if not src_parent.isValid() and parent.isValid():
                    # print("  index: passthrough, invalid src_parent")
                    return QModelIndex()
                # print("  index: passthrough, createIndex with None")
                return self.createIndex(row, col, None)
            except Exception:
                # print(f"  index: passthrough exception: {e}")
                return QModelIndex()

        # Top-level flattened row
        if not parent.isValid():
            if row >= len(self._rows) or col >= self.columnCount():
                # print("  index: top-level out of bounds")
                return QModelIndex()
            # print("  index: top-level createIndex with None")
            return self.createIndex(row, col, None)

        # Mixed hierarchy disabled - no children
        if not self._mixed:
            # print("  index: mixed hierarchy disabled")
            return QModelIndex()

        # Mixed hierarchy: children of flattened rows
        if parent.internalPointer() is None:
            if parent.row() >= len(self._rows):
                # print("  index: child-of-flat, parent.row out of bounds")
                return QModelIndex()
            rowinfo = self._rows[parent.row()]
            
            # Get the underlying QModelIndex from QPersistentModelIndex
            if not rowinfo.leaf.isValid():
                # print("  index: child-of-flat, rowinfo.leaf invalid")
                return QModelIndex()
            
            # Create a new QModelIndex from the persistent index data
            src_parent = rowinfo.leaf.model().index(
                rowinfo.leaf.row(),
                rowinfo.leaf.column(),
                QModelIndex()  # parent - we're dealing with flattened items
            )

            # Only allow column 0 for children to avoid crashes
            if col != 0:
                # print("  index: child-of-flat, col != 0")
                return QModelIndex()

            if row >= self.sourceModel().rowCount(src_parent):
                # print("  index: child-of-flat, row out of src_parent bounds")
                return QModelIndex()

            src_child = self.sourceModel().index(row, 0, src_parent)
            if not src_child.isValid():
                # print("  index: child-of-flat, src_child invalid")
                return QModelIndex()

            # Use the persistent source index directly as internal pointer
            persistent = QPersistentModelIndex(src_child)
            # Use hash of persistent index as internal pointer ID to avoid corruption
            child_id = hash(persistent) % 2147483647  # Keep within reasonable range
            if child_id < 0:
                child_id = -child_id
            if child_id == 0:
                child_id = 1  # Avoid 0 which Qt might interpret as None
            self._child_cache[child_id] = persistent
            # print(f"  index: child-of-flat, createIndex(row={row}, col={col}, ...")
            return self.createIndex(row, col, child_id)

        # Grandchildren or deeper
        elif parent.internalPointer() is not None:
            # Get the cached QPersistentModelIndex
            parent_id = parent.internalPointer()
            if not isinstance(parent_id, int) or parent_id not in self._child_cache:
                # print(f"  index: grandchild, bad parent_id: {parent_id}")
                return QModelIndex()
            
            try:
                parent_persistent = self._child_cache[parent_id]
                if not parent_persistent.isValid():
                    # print("  index: grandchild, parent_persistent invalid")
                    return QModelIndex()
                
                # Create a new QModelIndex from the QPersistentModelIndex
                src_parent = parent_persistent.model().index(
                    parent_persistent.row(),
                    parent_persistent.column(),
                    QModelIndex()  # parent - simplified for now
                )
                if not src_parent.isValid():
                    # print("  index: grandchild, src_parent invalid")
                    return QModelIndex()

                # Only allow column 0 for children to avoid crashes
                if col != 0:
                    # print("  index: grandchild, col != 0")
                    return QModelIndex()

                if row >= self.sourceModel().rowCount(src_parent):
                    # print("  index: grandchild, row out of src_parent bounds")
                    return QModelIndex()

                src_child = self.sourceModel().index(row, 0, src_parent)
                if not src_child.isValid():
                    # print("  index: grandchild, src_child invalid")
                    return QModelIndex()

                # Use ID-based system for grandchildren too
                child_id = hash(src_child) % 2147483647  # Keep within reasonable range
                if child_id < 0:
                    child_id = -child_id
                if child_id == 0:
                    child_id = 1  # Avoid 0 which Qt might interpret as None
                persistent = QPersistentModelIndex(src_child)
                self._child_cache[child_id] = persistent
                # print(f"  index: grandchild, createIndex(row={row}, col={col}, ...")
                return self.createIndex(row, col, child_id)
            except Exception:
                # print(f"  index: grandchild exception: {e}")
                return QModelIndex()

        # print("  index: fallback return invalid QModelIndex")
        return QModelIndex()

    def parent(self, child: QModelIndex) -> QModelIndex:
        # print(f"parent(child={child}, child.internalPointer={child.internalPointer() if child.isValid() else None})")
        if not child.isValid() or self._level < 0:
            # print("  parent: invalid child or passthrough")
            return QModelIndex()

        # If this is a top-level flattened row, it has no parent
        if child.internalPointer() is None:
            # print("  parent: top-level row, no parent")
            return QModelIndex()

        # If this is a mixed hierarchy child
        if self._mixed and child.internalPointer() is not None:
            child_id = child.internalPointer()
            if not isinstance(child_id, int) or child_id not in self._child_cache:
                # print(f"  parent: bad child_id: {child_id}")
                return QModelIndex()
            try:
                child_persistent = self._child_cache[child_id]
                if not child_persistent.isValid():
                    # print("  parent: child_persistent invalid")
                    return QModelIndex()
                
                # Create QModelIndex from QPersistentModelIndex properly
                src_child = child_persistent.model().index(
                    child_persistent.row(),
                    child_persistent.column(),
                    QModelIndex()  # simplified for now
                )
                src_parent = src_child.parent()

                # Check if the source parent is one of our flattened rows
                psrc_parent = QPersistentModelIndex(src_parent)
                if psrc_parent in self._src2row:
                    parent_row = self._src2row[psrc_parent]
                    # print(f"  parent: parent is top-level row {parent_row}")
                    return self.createIndex(parent_row, 0, None)

                # If not, this is a deeper level child
                if src_parent.isValid():
                    # Find the ID for the parent
                    parent_id = None
                    for cached_id, cached_persistent in self._child_cache.items():
                        if cached_persistent.isValid() and QModelIndex(cached_persistent) == src_parent:
                            parent_id = cached_id
                            break
                    
                    if parent_id is None:
                        # Create new hash-based ID for parent
                        parent_id = hash(src_parent) % 2147483647  # Keep within reasonable range
                        if parent_id < 0:
                            parent_id = -parent_id
                        if parent_id == 0:
                            parent_id = 1  # Avoid 0 which Qt might interpret as None
                        self._child_cache[parent_id] = QPersistentModelIndex(src_parent)
                    
                    print(f"  parent: deeper, createIndex({src_parent.row()}, 0, {parent_id})")
                    return self.createIndex(src_parent.row(), 0, parent_id)

            except Exception as e:
                print(f"  parent: exception: {e}")

        print("  parent: fallback return invalid QModelIndex")
        return QModelIndex()

    def mapToSource(self, proxy: QModelIndex) -> QModelIndex:
        # print(f"mapToSource(proxy={proxy}, proxy.internalPointer={proxy.internalPointer() if proxy.isValid() else None})")
        if not proxy.isValid() or not self.sourceModel():
            print("  mapToSource: invalid proxy or no sourceModel")
            return QModelIndex()

        if self._level < 0:
            # Pass-through mode
            try:
                print("  mapToSource: passthrough")
                return self.sourceModel().index(proxy.row(), proxy.column(), QModelIndex())
            except Exception as e:
                print(f"  mapToSource: passthrough exception: {e}")
                return QModelIndex()

        # Top-level flattened row showing hierarchical path
        if proxy.internalPointer() is None:
            if proxy.row() >= len(self._rows):
                print("  mapToSource: top-level, row out of bounds")
                return QModelIndex()
            row_info = self._rows[proxy.row()]
            # Return the ancestor at the requested column level
            if proxy.column() < len(row_info.ancestors):
                ancestor = row_info.ancestors[proxy.column()]
                # print(f"  mapToSource: top-level, ancestor={ancestor}")
                if isinstance(ancestor, QPersistentModelIndex) and ancestor.isValid():
                    return QModelIndex(ancestor)
            print("  mapToSource: top-level, fallback invalid")
            return QModelIndex()

        # Mixed hierarchy child
        if self._mixed and proxy.internalPointer() is not None:
            ip = proxy.internalPointer()
            if not isinstance(ip, int) or ip not in self._child_cache:
                print(f"  mapToSource: mixed, bad internalPointer: {ip}")
                return QModelIndex()
            try:
                cached_persistent = self._child_cache[ip]
                if not cached_persistent.isValid():
                    print("  mapToSource: mixed, cached_persistent invalid")
                    return QModelIndex()
                print(f"  mapToSource: mixed, returning QModelIndex({cached_persistent})")
                return QModelIndex(cached_persistent)
            except Exception as e:
                print(f"  mapToSource: mixed, exception: {e}")
                return QModelIndex()

        print("  mapToSource: fallback return invalid QModelIndex")
        return QModelIndex()

    def mapFromSource(self, src: QModelIndex) -> QModelIndex:
        if not src.isValid() or not self.sourceModel():
            return QModelIndex()

        if self._level < 0:
            # Pass-through mode
            try:
                return self.createIndex(src.row(), src.column(), None)
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
            # For mixed hierarchy, create index with source as internal pointer
            try:
                src_parent = src.parent()
                if not src_parent.isValid():
                    # src is a top-level item, check if it's in our flattened rows
                    if psrc in self._src2row:
                        row = self._src2row[psrc]
                        return self.index(row, 0)
                    return QModelIndex()
                else:
                    # src is a child - use hash-based system for internal pointer
                    child_id = hash(src) % 2147483647  # Keep within reasonable range
                    if child_id < 0:
                        child_id = -child_id
                    if child_id == 0:
                        child_id = 1  # Avoid 0 which Qt might interpret as None
                    self._child_cache[child_id] = QPersistentModelIndex(src)
                    return self.createIndex(src.row(), 0, child_id)
            except:
                return QModelIndex()

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

        # Create layout
        layout = QVBoxLayout(self)

        # Controls
        controls = QHBoxLayout()

        # Level selector
        controls.addWidget(QLabel("Flatten Level:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems([
            "Pass-through", "Level 0 - A", "Level 1 - B", "Level 2 - C", "Level 3 - D"
        ])
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
        self._on_level_changed(4)  # Level 3 - D
        self._on_mixed_changed(True)  # Try with mixed hierarchy

    def _populate_model(self):
        root = self.src_model.invisibleRootItem()
        for i in range(3):
            item_a = QStandardItem(f"A{i}")
            root.appendRow(item_a)
            for j in range(3):
                item_b = QStandardItem(f"B{j}")
                item_a.appendRow(item_b)
                for k in range(3):
                    item_c = QStandardItem(f"C{k}")
                    item_b.appendRow(item_c)
                    for l in range(3):
                        item_d = QStandardItem(f"D{l}")
                        item_c.appendRow(item_d)
                        for m in range(3):
                            item_e = QStandardItem(f"E{m}")
                            item_d.appendRow(item_e)

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
    sys.exit(app.exec())
