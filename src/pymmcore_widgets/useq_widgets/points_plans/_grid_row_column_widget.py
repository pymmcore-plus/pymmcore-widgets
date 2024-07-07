from __future__ import annotations

from typing import Mapping

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from useq import GridRowsColumns, OrderMode


class GridRowColumnWidget(QWidget):
    """Widget to generate a grid of FOVs within a specified area."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.fov_size: tuple[float | None, float | None] = (None, None)

        # title
        title = QLabel(text="Fields of View in a Grid.")
        title.setStyleSheet("font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # rows
        self._rows = QSpinBox()
        self._rows.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rows.setMinimum(1)
        # columns
        self._cols = QSpinBox()
        self._cols.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cols.setMinimum(1)
        # overlap along x
        self._overlap_x = QDoubleSpinBox()
        self._overlap_x.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._overlap_x.setRange(-10000, 100)
        # overlap along y
        self._overlap_y = QDoubleSpinBox()
        self._overlap_y.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._overlap_x.setRange(-10000, 100)
        # order combo
        self._order_combo = QComboBox()
        self._order_combo.addItems([mode.value for mode in OrderMode])
        self._order_combo.setCurrentText(OrderMode.row_wise_snake.value)

        # form layout
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setSpacing(5)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Rows:", self._rows)
        form.addRow("Columns:", self._cols)
        form.addRow("Overlap x (%):", self._overlap_x)
        form.addRow("Overlap y (%):", self._overlap_y)
        form.addRow("Grid Order:", self._order_combo)

        # main
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(title)
        main_layout.addLayout(form)

        # connect
        self._rows.valueChanged.connect(self._on_value_changed)
        self._cols.valueChanged.connect(self._on_value_changed)
        self._overlap_x.valueChanged.connect(self._on_value_changed)
        self._overlap_y.valueChanged.connect(self._on_value_changed)
        self._order_combo.currentTextChanged.connect(self._on_value_changed)

    def _on_value_changed(self) -> None:
        """Emit the valueChanged signal."""
        self.valueChanged.emit(self.value())

    def value(self) -> GridRowsColumns:
        """Return the values of the widgets."""
        fov_x, fov_y = self.fov_size
        return GridRowsColumns(
            rows=self._rows.value(),
            columns=self._cols.value(),
            overlap=(self._overlap_x.value(), self._overlap_y.value()),
            mode=self._order_combo.currentText(),
            fov_width=fov_x,
            fov_height=fov_y,
        )

    def setValue(self, value: GridRowsColumns | Mapping) -> None:
        """Set the values of the widgets."""
        value = GridRowsColumns.model_validate(value)
        self._rows.setValue(value.rows)
        self._cols.setValue(value.columns)
        self._overlap_x.setValue(value.overlap[0])
        self._overlap_y.setValue(value.overlap[1])
        self._order_combo.setCurrentText(value.mode.value)
        self.fov_size = (value.fov_width, value.fov_height)

    def reset(self) -> None:
        """Reset value to 1x1, row-wise-snake, with 0 overlap."""
        self._rows.setValue(1)
        self._cols.setValue(1)
        self._overlap_x.setValue(0)
        self._overlap_y.setValue(0)
        self._order_combo.setCurrentText(OrderMode.row_wise_snake.value)
        self.fov_size = (None, None)
