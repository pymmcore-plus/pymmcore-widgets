import sys
from enum import Enum
from typing import NamedTuple

from PyQt6.QtCore import QAbstractProxyModel, QModelIndex, Qt
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QTableView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


class FlattenMode(Enum):
    FLATTEN_TO_LEVEL = "flatten_to_level"
    FLATTEN_WITH_EXPANSION = "flatten_with_expansion"


class FlattenedItem(NamedTuple):
    source_index: QModelIndex
    path: list[QModelIndex]
    is_expanded: bool
    display_level: int


class TreeFlatteningProxyModel(QAbstractProxyModel):
    """
    A proxy model that flattens a tree structure to show specified levels
    as rows in a table format.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._flattened_items: list[FlattenedItem] = []
        self._flatten_depth = 0
        self._mode = FlattenMode.FLATTEN_TO_LEVEL
        self._secondary_depth = -1  # For expandable mode

    def setSourceModel(self, model):
        """Set the source model and rebuild the flattened structure."""
        if self.sourceModel():
            self.sourceModel().dataChanged.disconnect(self._on_source_data_changed)
            self.sourceModel().rowsInserted.disconnect(self._on_source_rows_inserted)
            self.sourceModel().rowsRemoved.disconnect(self._on_source_rows_removed)
            self.sourceModel().modelReset.disconnect(self._on_source_model_reset)

        super().setSourceModel(model)

        if model:
            model.dataChanged.connect(self._on_source_data_changed)
            model.rowsInserted.connect(self._on_source_rows_inserted)
            model.rowsRemoved.connect(self._on_source_rows_removed)
            model.modelReset.connect(self._on_source_model_reset)

        self._rebuild_flattened_structure()

    def set_flatten_depth(self, depth: int):
        """Set the depth level to flatten to."""
        self._flatten_depth = depth
        self._rebuild_flattened_structure()

    def set_flatten_mode(self, mode: FlattenMode):
        """Set the flattening mode."""
        self._mode = mode
        self._rebuild_flattened_structure()

    def set_flatten_configuration(self, primary_level: int, secondary_level: int = -1):
        """Set both primary and secondary levels for complex flattening."""
        self._flatten_depth = primary_level
        self._secondary_depth = secondary_level
        self._rebuild_flattened_structure()

    def _rebuild_flattened_structure(self):
        """Rebuild the entire flattened structure."""
        self.beginResetModel()
        self._flattened_items.clear()

        if not self.sourceModel():
            self.endResetModel()
            return

        self._build_flattened_items(QModelIndex(), [], 0)
        self.endResetModel()

    def _build_flattened_items(
        self, parent: QModelIndex, current_path: list[QModelIndex], current_depth: int
    ):
        """Recursively build the flattened items structure."""
        if not self.sourceModel():
            return

        row_count = self.sourceModel().rowCount(parent)

        for i in range(row_count):
            child = self.sourceModel().index(i, 0, parent)
            if not child.isValid():
                continue

            child_path = [*current_path, child]

            # Check if this is our target level
            if current_depth == self._flatten_depth:
                item = FlattenedItem(
                    source_index=child,
                    path=child_path,
                    is_expanded=False,
                    display_level=current_depth,
                )
                self._flattened_items.append(item)

            # For expandable mode, also add intermediate levels
            elif (
                self._mode == FlattenMode.FLATTEN_WITH_EXPANSION
                and self._secondary_depth != -1
                and current_depth == self._secondary_depth
            ):
                item = FlattenedItem(
                    source_index=child,
                    path=child_path,
                    is_expanded=False,
                    display_level=current_depth,
                )
                self._flattened_items.append(item)

            # Continue recursion if there are children
            if self.sourceModel().hasChildren(child):
                self._build_flattened_items(child, child_path, current_depth + 1)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of flattened items."""
        if parent.isValid():
            return 0  # Flat structure, no children
        return len(self._flattened_items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of columns (levels in the path)."""
        if not self._flattened_items:
            return 0
        return self._flatten_depth + 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """Return data for the given index."""
        if not index.isValid() or index.row() >= len(self._flattened_items):
            return None

        item = self._flattened_items[index.row()]

        # Map columns to different levels of the path
        if index.column() < len(item.path):
            source_idx = item.path[index.column()]
            return self.sourceModel().data(source_idx, role)

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        """Return header data."""
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return f"Level {section}"
        return None

    def index(
        self, row: int, column: int, parent: QModelIndex = QModelIndex()
    ) -> QModelIndex:
        """Create an index for the given row and column."""
        if (
            parent.isValid()
            or row < 0
            or row >= len(self._flattened_items)
            or column < 0
            or column >= self.columnCount()
        ):
            return QModelIndex()

        return self.createIndex(row, column, row)  # Use row as internal pointer

    def parent(self, index: QModelIndex) -> QModelIndex:
        """Return parent index (always invalid for flat structure)."""
        return QModelIndex()

    def mapToSource(self, proxy_index: QModelIndex) -> QModelIndex:
        """Map proxy index to source index."""
        if not proxy_index.isValid() or proxy_index.row() >= len(self._flattened_items):
            return QModelIndex()

        item = self._flattened_items[proxy_index.row()]
        if proxy_index.column() < len(item.path):
            return item.path[proxy_index.column()]

        return QModelIndex()

    def mapFromSource(self, source_index: QModelIndex) -> QModelIndex:
        """Map source index to proxy index."""
        if not source_index.isValid():
            return QModelIndex()

        # Find the flattened item that contains this source index
        for row, item in enumerate(self._flattened_items):
            if source_index in item.path:
                col = item.path.index(source_index)
                return self.index(row, col)

        return QModelIndex()

    def toggle_expansion(self, proxy_index: QModelIndex):
        """Toggle expansion state for expandable items."""
        if not proxy_index.isValid() or proxy_index.row() >= len(self._flattened_items):
            return

        # This is where you'd implement expansion logic
        # For now, just rebuild - in a real implementation you'd be more selective
        self._rebuild_flattened_structure()

    # Source model change handlers
    def _on_source_data_changed(
        self, top_left: QModelIndex, bottom_right: QModelIndex, roles: list[int]
    ):
        """Handle source model data changes."""
        # Simple approach: rebuild everything
        # In a real implementation, you'd be more selective
        self._rebuild_flattened_structure()

    def _on_source_rows_inserted(self, parent: QModelIndex, first: int, last: int):
        """Handle source model row insertion."""
        self._rebuild_flattened_structure()

    def _on_source_rows_removed(self, parent: QModelIndex, first: int, last: int):
        """Handle source model row removal."""
        self._rebuild_flattened_structure()

    def _on_source_model_reset(self):
        """Handle source model reset."""
        self._rebuild_flattened_structure()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    class TreeFlatteningDemo(QMainWindow):
        """Demo application showing the tree flattening proxy model in action."""

        def __init__(self):
            super().__init__()
            self.setWindowTitle("Tree Flattening Proxy Model Demo")
            self.setGeometry(100, 100, 800, 600)

            # Create the source model with sample data
            self.source_model = self._create_sample_model()

            # Create the proxy model
            self.proxy_model = TreeFlatteningProxyModel()
            self.proxy_model.setSourceModel(self.source_model)

            self._setup_ui()

            # Set initial configuration
            self.proxy_model.set_flatten_depth(4)  # Show all E's

        def _create_sample_model(self) -> QStandardItemModel:
            """Create a sample tree model with A>B>C>D>E structure."""
            model = QStandardItemModel()
            model.setHorizontalHeaderLabels(["Name"])

            # Create sample data: A > B > C > D > E
            for a_idx in range(2):
                item_a = QStandardItem(f"A{a_idx + 1}")
                model.appendRow(item_a)

                for b_idx in range(3):
                    item_b = QStandardItem(f"B{b_idx + 1}")
                    item_a.appendRow(item_b)

                    for c_idx in range(2):
                        item_c = QStandardItem(f"C{c_idx + 1}")
                        item_b.appendRow(item_c)

                        for d_idx in range(2):
                            item_d = QStandardItem(f"D{d_idx + 1}")
                            item_c.appendRow(item_d)

                            for e_idx in range(3):
                                item_e = QStandardItem(f"E{e_idx + 1}")
                                item_d.appendRow(item_e)

            return model

        def _setup_ui(self):
            """Setup the user interface."""
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            layout = QVBoxLayout(central_widget)

            # Control buttons
            button_layout = QHBoxLayout()

            btn_show_all_e = QPushButton("Show All E's")
            btn_show_all_e.clicked.connect(
                lambda: self.proxy_model.set_flatten_depth(4)
            )

            btn_show_all_d = QPushButton("Show All D's")
            btn_show_all_d.clicked.connect(
                lambda: self.proxy_model.set_flatten_depth(3)
            )

            btn_show_all_c = QPushButton("Show All C's")
            btn_show_all_c.clicked.connect(
                lambda: self.proxy_model.set_flatten_depth(2)
            )

            btn_show_all_b = QPushButton("Show All B's")
            btn_show_all_b.clicked.connect(
                lambda: self.proxy_model.set_flatten_depth(1)
            )

            button_layout.addWidget(btn_show_all_e)
            button_layout.addWidget(btn_show_all_d)
            button_layout.addWidget(btn_show_all_c)
            button_layout.addWidget(btn_show_all_b)

            layout.addLayout(button_layout)

            # Views layout
            views_layout = QHBoxLayout()

            # Original tree view
            self.tree_view = QTreeView()
            self.tree_view.setModel(self.source_model)
            self.tree_view.expandAll()

            # Flattened table view
            self.table_view = QTableView()
            self.table_view.setModel(self.proxy_model)
            self.table_view.setSortingEnabled(True)

            views_layout.addWidget(self.tree_view)
            views_layout.addWidget(self.table_view)

            layout.addLayout(views_layout)

    demo = TreeFlatteningDemo()
    demo.show()

    sys.exit(app.exec())
