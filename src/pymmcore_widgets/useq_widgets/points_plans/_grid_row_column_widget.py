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

        self.fov_width: float | None = None
        self.fov_height: float | None = None
        self._relative_to: str = "center"

        # title
        title = QLabel(text="Fields of View in a Grid")
        title.setStyleSheet("font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # rows
        self.rows = QSpinBox()
        self.rows.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rows.setMinimum(1)
        self.rows.setValue(3)
        # columns
        self.columns = QSpinBox()
        self.columns.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.columns.setMinimum(1)
        self.columns.setValue(3)
        # overlap along x
        self.overlap_x = QDoubleSpinBox()
        self.overlap_x.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlap_x.setRange(-10000, 100)
        # overlap along y
        self.overlap_y = QDoubleSpinBox()
        self.overlap_y.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlap_y.setRange(-10000, 100)
        # order combo
        self.mode = QComboBox()
        self.mode.addItems([mode.value for mode in OrderMode])
        self.mode.setCurrentText(OrderMode.row_wise_snake.value)

        # form layout
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setSpacing(5)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Rows:", self.rows)
        form.addRow("Columns:", self.columns)
        form.addRow("Overlap x (%):", self.overlap_x)
        form.addRow("Overlap y (%):", self.overlap_y)
        form.addRow("Grid Order:", self.mode)

        # main
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(title)
        main_layout.addLayout(form)

        # connect
        self.rows.valueChanged.connect(self._on_value_changed)
        self.columns.valueChanged.connect(self._on_value_changed)
        self.overlap_x.valueChanged.connect(self._on_value_changed)
        self.overlap_y.valueChanged.connect(self._on_value_changed)
        self.mode.currentTextChanged.connect(self._on_value_changed)

    def _on_value_changed(self) -> None:
        """Emit the valueChanged signal."""
        self.valueChanged.emit(self.value())

    @property
    def overlap(self) -> tuple[float, float]:
        """Return the overlap along x and y."""
        return self.overlap_x.value(), self.overlap_y.value()

    @property
    def fov_size(self) -> tuple[float | None, float | None]:
        """Return the FOV size in (width, height)."""
        return self.fov_width, self.fov_height

    @fov_size.setter
    def fov_size(self, size: tuple[float | None, float | None]) -> None:
        """Set the FOV size."""
        self.fov_width, self.fov_height = size

    def value(self) -> GridRowsColumns:
        """Return the values of the widgets."""
        return GridRowsColumns(
            rows=self.rows.value(),
            columns=self.columns.value(),
            overlap=self.overlap,
            mode=self.mode.currentText(),
            fov_width=self.fov_width,
            fov_height=self.fov_height,
            relative_to=self._relative_to,
        )

    def setValue(self, value: GridRowsColumns | Mapping) -> None:
        """Set the values of the widgets."""
        value = GridRowsColumns.model_validate(value)
        self.rows.setValue(value.rows)
        self.columns.setValue(value.columns)
        self.overlap_x.setValue(value.overlap[0])
        self.overlap_y.setValue(value.overlap[1])
        self.mode.setCurrentText(value.mode.value)
        self.fov_width = value.fov_width
        self.fov_height = value.fov_height
        self._relative_to = value.relative_to.value

    def reset(self) -> None:
        """Reset value to 1x1, row-wise-snake, with 0 overlap."""
        self.rows.setValue(1)
        self.columns.setValue(1)
        self.overlap_x.setValue(0)
        self.overlap_y.setValue(0)
        self.mode.setCurrentText(OrderMode.row_wise_snake.value)
        self.fov_size = (None, None)
