from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from pymmcore_widgets._models._tree_flattening import TreeFlatteningProxy


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
        self.proxy = TreeFlatteningProxy(row_depth=0)
        self.proxy.setSourceModel(src_model)

        self.tree2 = tree2 = QtWidgets.QTreeView()
        tree2.setAlternatingRowColors(True)
        tree2.setSortingEnabled(True)
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
