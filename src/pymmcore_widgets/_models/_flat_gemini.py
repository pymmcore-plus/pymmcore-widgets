import sys

from PyQt6.QtCore import (
    QAbstractProxyModel,
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


class TreeFlatteningProxyModel(QAbstractProxyModel):
    """
    A proxy model that can flatten a source tree model to an arbitrary depth
    or present a mixed hierarchy.

    - Level -1 (Default): Pass-through, acts like a normal tree.
    - Level 0: Flatten at level 'A'. Each row is an 'A' item.
    - Level 1: Flatten at level 'B'. Each row is a 'B' item.
    ...and so on.

    When a level is chosen for flattening, all ancestor data is presented
    in columns. For levels below the flattening level, the model can
    expose the hierarchy, allowing a QTreeView to expand/collapse children.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._flattening_level = -1
        # _source_map will store QPersistentModelIndex objects of the source items
        # that should be treated as top-level rows in the proxy.
        self._source_map = []

    def setFlatteningLevel(self, level):
        """
        Sets the depth to which the source model is flattened.
        -1 means no flattening (pass-through).
        0 means flatten at the root level, 1 at the next, etc.
        """
        if self._flattening_level == level:
            return

        self.beginResetModel()
        self._flattening_level = level
        self._source_map.clear()

        if self._flattening_level > -1:
            # Build the map of source indexes that will become our top-level rows.
            self._build_map_recursive(self.sourceModel().invisibleRootItem().index(), 0)

        self.endResetModel()

    def _build_map_recursive(self, parent_source_index, depth):
        """
        Recursively traverses the source model to find all items
        at the target flattening level.
        """
        source_model = self.sourceModel()
        for row in range(source_model.rowCount(parent_source_index)):
            child_source_index = source_model.index(row, 0, parent_source_index)
            if not child_source_index.isValid():
                continue

            if depth == self._flattening_level:
                # We found an item at the target level. Add it to our map.
                # Use QPersistentModelIndex because the source model could change.
                self._source_map.append(QPersistentModelIndex(child_source_index))
            elif depth < self._flattening_level:
                # We haven't reached the target depth yet, so go deeper.
                self._build_map_recursive(child_source_index, depth + 1)

    def mapToSource(self, proxy_index):
        """Maps a proxy index back to its corresponding source index."""
        if not proxy_index.isValid() or self.sourceModel() is None:
            return QModelIndex()

        # Pass-through mode
        if self._flattening_level == -1:
            return self.sourceModel().index(
                proxy_index.row(),
                proxy_index.column(),
                self.mapToSource(proxy_index.parent()),
            )

        # The internal pointer of a proxy index is our secret weapon.
        # We use it to store the original source index for child items in a mixed hierarchy.
        source_item_index = proxy_index.internalPointer()

        if source_item_index and source_item_index.isValid():
            # This is a child of a flattened item (e.g., a 'C' under a 'B' row).
            # The pointer IS the source index.
            return source_item_index

        # This is a top-level flattened item. We need to calculate the source index.
        if 0 <= proxy_index.row() < len(self._source_map):
            base_source_index = self._source_map[proxy_index.row()]

            # Traverse up the tree from the base source index to find the
            # correct ancestor for the requested column.
            source_index = base_source_index
            for _ in range(self._flattening_level - proxy_index.column()):
                source_index = source_index.parent()
            return source_index

        return QModelIndex()

    def mapFromSource(self, source_index):
        """Maps a source index to its corresponding proxy index."""
        if not source_index.isValid() or self.sourceModel() is None:
            return QModelIndex()

        # Pass-through mode
        if self._flattening_level == -1:
            source_parent = source_index.parent()
            proxy_parent = self.mapFromSource(source_parent)
            return self.index(source_index.row(), source_index.column(), proxy_parent)

        # Find the item's ancestor that is at the flattening level.
        ancestor_at_flattening_level = source_index
        while (
            ancestor_at_flattening_level.isValid()
            and ancestor_at_flattening_level.internalId() > 0
        ):  # a bit of a heuristic check
            parent = ancestor_at_flattening_level.parent()
            if (
                not parent.isValid()
                or parent == self.sourceModel().invisibleRootItem().index()
            ):
                break  # Reached the top
            if (
                len(self.sourceModel().data(parent, Qt.ItemDataRole.DisplayRole)) == 1
            ):  # Heuristic for depth
                break
            ancestor_at_flattening_level = parent

        try:
            # Find which row this ancestor corresponds to in our map.
            proxy_row = self._source_map.index(
                QPersistentModelIndex(ancestor_at_flattening_level)
            )
        except ValueError:
            return QModelIndex()  # Not found in our map.

        # Now determine if this is a top-level item or a child.
        if ancestor_at_flattening_level == source_index:
            # It's a top-level item. Column is its depth.
            return self.createIndex(proxy_row, source_index.column(), None)
        else:
            # It's a child of a top-level item.
            return self.createIndex(
                source_index.row(), source_index.column(), source_index
            )

    def rowCount(self, parent_proxy_index=QModelIndex()):
        """Returns the number of rows under the given parent."""
        if self.sourceModel() is None:
            return 0

        # Pass-through mode
        if self._flattening_level == -1:
            return self.sourceModel().rowCount(self.mapToSource(parent_proxy_index))

        if not parent_proxy_index.isValid():
            # Requesting number of top-level items.
            return len(self._source_map)

        # Requesting number of children for an expanded item.
        parent_source_index = self.mapToSource(parent_proxy_index)
        return self.sourceModel().rowCount(parent_source_index)

    def columnCount(self, parent_proxy_index=QModelIndex()):
        """Returns the number of columns."""
        if self.sourceModel() is None:
            return 0

        # Pass-through mode
        if self._flattening_level == -1:
            return self.sourceModel().columnCount(self.mapToSource(parent_proxy_index))

        # We show one column for each level down to the flattening level.
        return self._flattening_level + 1

    def parent(self, proxy_child_index):
        """Returns the parent of the given proxy index."""
        if not proxy_child_index.isValid() or self._flattening_level == -1:
            return QModelIndex()

        source_child_index = self.mapToSource(proxy_child_index)
        if not source_child_index.isValid():
            return QModelIndex()

        source_parent_index = source_child_index.parent()

        # Check if the source parent is one of our top-level items.
        try:
            # Find the row in our map that corresponds to the source parent.
            proxy_row = self._source_map.index(
                QPersistentModelIndex(source_parent_index)
            )
            # If found, create a proxy index for it. This is the parent.
            return self.createIndex(proxy_row, 0, None)  # Parent is a top-level item
        except ValueError:
            # The parent is not a top-level item, so this child has no visible parent in the proxy.
            return QModelIndex()

    def index(self, row, column, parent_proxy_index=QModelIndex()):
        """Creates a proxy index for the given row, column, and parent."""
        if not self.hasIndex(row, column, parent_proxy_index):
            return QModelIndex()

        # Pass-through mode
        if self._flattening_level == -1:
            source_parent_index = self.mapToSource(parent_proxy_index)
            source_child_index = self.sourceModel().index(
                row, column, source_parent_index
            )
            return self.mapFromSource(source_child_index)

        if not parent_proxy_index.isValid():
            # Creating an index for a top-level item.
            # We don't need to store anything in the internal pointer for these.
            return self.createIndex(row, column, None)
        else:
            # Creating an index for a child of an expanded item.
            # We store the child's *source model index* in the internal pointer.
            # This is the key to linking back correctly in mapToSource.
            parent_source_index = self.mapToSource(parent_proxy_index)
            child_source_index = self.sourceModel().index(row, 0, parent_source_index)
            return self.createIndex(row, column, child_source_index)

    def data(self, proxy_index, role=Qt.ItemDataRole.DisplayRole):
        """Returns the data for a given proxy index."""
        if not proxy_index.isValid() or self.sourceModel() is None:
            return None

        source_index = self.mapToSource(proxy_index)
        if source_index.isValid():
            return self.sourceModel().data(source_index, role)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        """Returns the header data."""
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            if self._flattening_level == -1:
                return self.sourceModel().headerData(section, orientation, role)

            if 0 <= section <= self._flattening_level:
                # Create headers like 'A', 'B', 'C'...
                return chr(ord("A") + section)
        return super().headerData(section, orientation, role)


if __name__ == "__main__":

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Dynamic Flattening Proxy Model Demo")
            self.setGeometry(100, 100, 1000, 700)

            # Main widget and layout
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            layout = QVBoxLayout(central_widget)

            # 1. Create the source model
            self.source_model = self._create_source_model()

            # 2. Create our custom flattening proxy
            self.flattening_proxy = TreeFlatteningProxyModel()
            self.flattening_proxy.setSourceModel(self.source_model)

            # 3. Create a standard sort/filter proxy to chain them
            self.sort_filter_proxy = QSortFilterProxyModel()
            # IMPORTANT: The source for the sort/filter proxy is our custom proxy
            self.sort_filter_proxy.setSourceModel(self.flattening_proxy)
            self.sort_filter_proxy.setFilterCaseSensitivity(
                Qt.CaseSensitivity.CaseInsensitive
            )
            self.sort_filter_proxy.setFilterKeyColumn(-1)  # Filter on all columns

            # 4. Create the view
            self.view = QTreeView()
            # IMPORTANT: The view's model is the final proxy in the chain
            self.view.setModel(self.sort_filter_proxy)
            self.view.setSortingEnabled(True)
            self.view.setAlternatingRowColors(True)
            self.view.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

            # 5. Create controls
            controls_layout = QVBoxLayout()

            # Control for filtering
            filter_label = QLabel("Filter Table/Tree:")
            self.filter_input = QLineEdit()
            self.filter_input.textChanged.connect(
                self.sort_filter_proxy.setFilterRegularExpression
            )

            # Control for changing flattening level
            level_label = QLabel("Select Flattening Level:")
            self.level_combo = QComboBox()
            self.level_combo.addItems(
                [
                    "Disabled (Standard Tree View)",
                    "Level 0 (Rows of A)",
                    "Level 1 (Rows of B)",
                    "Level 2 (Rows of C)",
                    "Level 3 (Rows of D)",
                    "Level 4 (Rows of E - Full Flatten)",
                ]
            )
            self.level_combo.currentIndexChanged.connect(self.level_changed)

            controls_layout.addWidget(filter_label)
            controls_layout.addWidget(self.filter_input)
            controls_layout.addWidget(level_label)
            controls_layout.addWidget(self.level_combo)

            layout.addLayout(controls_layout)
            layout.addWidget(self.view)

            # Initialize view
            self.level_changed(0)

        def _create_source_model(self):
            """Creates and populates a 5-level deep QStandardItemModel."""
            model = QStandardItemModel()
            model.setHorizontalHeaderLabels(
                ["Data"]
            )  # Only one column in the source model

            root = model.invisibleRootItem()
            for i in range(3):  # A
                item_a = QStandardItem(f"A{i + 1}")
                root.appendRow(item_a)
                for j in range(2):  # B
                    item_b = QStandardItem(f"B{i * 2 + j + 1}")
                    item_a.appendRow(item_b)
                    for k in range(2):  # C
                        item_c = QStandardItem(f"C{i * 4 + j * 2 + k + 1}")
                        item_b.appendRow(item_c)
                        # Make D and E levels a bit irregular
                        for l in range(1 + (j % 2)):  # D
                            item_d = QStandardItem(f"D{i * 8 + j * 4 + k * 2 + l + 1}")
                            item_c.appendRow(item_d)
                            for m in range(2 + (k % 2)):  # E
                                item_e = QStandardItem(
                                    f"E{i * 16 + j * 8 + k * 4 + l * 2 + m + 1}"
                                )
                                item_d.appendRow(item_e)
            return model

        def level_changed(self, index):
            """Slot to handle the user changing the flattening level."""
            level = index - 1
            self.flattening_proxy.setFlatteningLevel(level)

            # Adjust view properties for better user experience
            if level == -1:
                # Standard tree view
                self.view.header().setVisible(False)
                self.view.expandAll()
            else:
                # Table-like view
                self.view.header().setVisible(True)
                self.view.expandAll()  # Expand to see children in mixed-hierarchy views
                self.view.header().setSectionResizeMode(
                    QHeaderView.ResizeMode.ResizeToContents
                )
                self.view.header().setStretchLastSection(True)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
