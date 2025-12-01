"""Example script to test the new PropertyWidget implementation."""

from __future__ import annotations

import sys

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QDialog,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets.device_properties._property_widget import PropertyWidget


class PropertyBrowser2(QDialog):
    """A simple property browser using the new PropertyWidget implementation."""

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Property Browser (v2)")
        self.resize(800, 600)

        self._mmc = mmcore or CMMCorePlus.instance()

        # Filter text box
        self._filter_text = QLineEdit()
        self._filter_text.setClearButtonEnabled(True)
        self._filter_text.setPlaceholderText("Filter by device or property name...")
        self._filter_text.textChanged.connect(self._apply_filter)

        # Property table
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Property", "Value"])
        self._table.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self._filter_text)
        layout.addWidget(self._table)

        self._build_table()

    def _build_table(self) -> None:
        """Build the property table."""
        self._table.clearContents()

        props = list(self._mmc.iterProperties(as_object=True))
        self._table.setRowCount(len(props))

        for row, prop in enumerate(props):
            # Property name column
            name = f"{prop.device} :: {prop.name}"
            if prop.isPreInit():
                name += " (pre-init)"
            item = QTableWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, (prop.device, prop.name))
            self._table.setItem(row, 0, item)

            # Widget column
            try:
                wdg = PropertyWidget(
                    prop.device,
                    prop.name,
                    mmcore=self._mmc,
                    connect_core=True,
                )
                self._table.setCellWidget(row, 1, wdg)

                # Gray out read-only rows
                if prop.isReadOnly():
                    item.setBackground(QColor("#DDD"))
                    wdg.setStyleSheet("QLabel { background-color: #DDD; }")
            except Exception as e:
                print(f"Error creating widget for {prop.device}::{prop.name}: {e}")

        self._table.resizeColumnsToContents()

    def _apply_filter(self, text: str) -> None:
        """Filter rows based on text."""
        text = text.lower()
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item:
                visible = not text or text in item.text().lower()
                self._table.setRowHidden(row, not visible)


def main() -> None:
    """Entry point for the example script."""
    app = QApplication(sys.argv)

    # Load demo configuration
    mmc = CMMCorePlus.instance()
    mmc.loadSystemConfiguration()

    # Print some info about what we loaded
    print("\n=== Loaded Properties ===")
    for prop in mmc.iterProperties(as_object=True):
        ptype = prop.type().name
        has_limits = prop.hasLimits()
        allowed = prop.allowedValues()
        info = f"  type={ptype}"
        if has_limits:
            info += f", limits={prop.range()}"
        if allowed:
            info += f", allowed={len(allowed)} values"
        if prop.isReadOnly():
            info += ", read-only"
        print(f"{prop.device}::{prop.name}: {info}")

    print("\n=== Starting GUI ===\n")

    browser = PropertyBrowser2()
    browser.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
