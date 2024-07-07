from __future__ import annotations

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from useq import GridRowsColumns
from useq._grid import OrderMode

AlignCenter = Qt.AlignmentFlag.AlignCenter
EXPANDING_W = (QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class GridRowColumnWidget(QGroupBox):
    """Widget to generate a grid of FOVs within a specified area."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._fov_size: tuple[float | None, float | None] = (None, None)

        # title
        title = QLabel(text="Fields of Views in a Grid.")
        title.setStyleSheet("font-weight: bold;")
        title.setAlignment(AlignCenter)
        # rows
        self._rows = QSpinBox()
        self._rows.setSizePolicy(*EXPANDING_W)
        self._rows.setAlignment(AlignCenter)
        self._rows.setMinimum(1)
        # columns
        self._cols = QSpinBox()
        self._cols.setSizePolicy(*EXPANDING_W)
        self._cols.setAlignment(AlignCenter)
        self._cols.setMinimum(1)
        # overlap along x
        self._overlap_x = QDoubleSpinBox()
        self._overlap_x.setSizePolicy(*EXPANDING_W)
        self._overlap_x.setAlignment(AlignCenter)
        self._overlap_x.setMinimum(-10000)
        self._overlap_x.setMaximum(100)
        self._overlap_x.setSingleStep(1.0)
        self._overlap_x.setValue(0)
        # overlap along y
        self._overlap_y = QDoubleSpinBox()
        self._overlap_y.setSizePolicy(*EXPANDING_W)
        self._overlap_y.setAlignment(AlignCenter)
        self._overlap_y.setMinimum(-10000)
        self._overlap_y.setMaximum(100)
        self._overlap_y.setSingleStep(1.0)
        self._overlap_y.setValue(0)
        # order combo
        self._order_combo = QComboBox()
        self._order_combo.setSizePolicy(*EXPANDING_W)
        self._order_combo.addItems([mode.value for mode in OrderMode])
        self._order_combo.setCurrentText(OrderMode.row_wise_snake.value)
        # form layout
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        form_layout.setSpacing(5)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.addRow(QLabel("Rows:"), self._rows)
        form_layout.addRow(QLabel("Columns:"), self._cols)
        form_layout.addRow(QLabel("Overlap x (%):"), self._overlap_x)
        form_layout.addRow(QLabel("Overlap y (%):"), self._overlap_y)
        form_layout.addRow(QLabel("Grid Order:"), self._order_combo)

        # main
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(title)
        main_layout.addLayout(form_layout)

        # connect
        self._rows.valueChanged.connect(self._on_value_changed)
        self._cols.valueChanged.connect(self._on_value_changed)
        self._overlap_x.valueChanged.connect(self._on_value_changed)
        self._overlap_y.valueChanged.connect(self._on_value_changed)
        self._order_combo.currentTextChanged.connect(self._on_value_changed)

    @property
    def fov_size(self) -> tuple[float | None, float | None]:
        """Return the FOV size."""
        return self._fov_size

    @fov_size.setter
    def fov_size(self, size: tuple[float | None, float | None]) -> None:
        """Set the FOV size."""
        self._fov_size = size

    def _on_value_changed(self) -> None:
        """Emit the valueChanged signal."""
        self.valueChanged.emit(self.value())

    def value(self) -> GridRowsColumns:
        """Return the values of the widgets."""
        fov_x, fov_y = self._fov_size
        return GridRowsColumns(
            rows=self._rows.value(),
            columns=self._cols.value(),
            overlap=(self._overlap_x.value(), self._overlap_y.value()),
            mode=self._order_combo.currentText(),
            fov_width=fov_x,
            fov_height=fov_y,
        )

    def setValue(self, value: GridRowsColumns) -> None:
        """Set the values of the widgets."""
        self._rows.setValue(value.rows)
        self._cols.setValue(value.columns)
        self._overlap_x.setValue(value.overlap[0])
        self._overlap_y.setValue(value.overlap[1])
        self._order_combo.setCurrentText(value.mode.value)
        self.fov_size = (value.fov_width, value.fov_height)

    def reset(self) -> None:
        """Reset the values of the widgets."""
        self._rows.setValue(1)
        self._cols.setValue(1)
        self._overlap_x.setValue(0)
        self._overlap_y.setValue(0)
        self._fov_size = (None, None)
