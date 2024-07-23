from __future__ import annotations

import random
from typing import Mapping

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from useq import RandomPoints, Shape, TraversalOrder


class RandomPointWidget(QWidget):
    """Widget to generate random points within a specified area."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # NON-GUI attributes

        self._start_at: int = 0

        # setting a random seed for point generation reproducibility
        self.random_seed: int = self._new_seed()
        self._fov_size: tuple[float | None, float | None] = (None, None)

        # title
        title = QLabel(text="Random Points")
        title.setStyleSheet("font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # well area doublespinbox along x
        self.max_width = QDoubleSpinBox()
        self.max_width.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.max_width.setRange(1, 1000000)
        self.max_width.setValue(6000)
        self.max_width.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
        # well area doublespinbox along y
        self.max_height = QDoubleSpinBox()
        self.max_height.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.max_height.setRange(1, 1000000)
        self.max_height.setValue(6000)
        self.max_height.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
        # number of FOVs spinbox
        self.num_points = QSpinBox()
        self.num_points.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.num_points.setRange(1, 1000)
        self.num_points.setValue(10)
        # order combobox
        self.order = QComboBox()
        self.order.addItems([mode.value for mode in TraversalOrder])
        self.order.setCurrentText(TraversalOrder.TWO_OPT.value)
        # allow overlap checkbox
        self.allow_overlap = QCheckBox()
        # random button
        self._random_button = QPushButton(text="Randomize")

        self.shape = QComboBox()
        self.shape.addItems([mode.value for mode in Shape])
        self.shape.setCurrentText(Shape.ELLIPSE.value)

        self.order = QComboBox()
        self.order.addItems([mode.value for mode in TraversalOrder])
        self.order.setCurrentText(TraversalOrder.TWO_OPT.value)

        # form layout
        self.form = form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setSpacing(5)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Width (µm):", self.max_width)
        form.addRow("Height (µm):", self.max_height)
        form.addRow("Num Points:", self.num_points)
        form.addRow("Order:", self.order)
        form.addRow("Shape:", self.shape)
        form.addRow("Allow Overlap:", self.allow_overlap)

        # main
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(title)
        main_layout.addLayout(form)
        main_layout.addWidget(self._random_button)

        # connect
        self.max_width.valueChanged.connect(self._on_value_changed)
        self.max_height.valueChanged.connect(self._on_value_changed)
        self.num_points.valueChanged.connect(self._on_value_changed)
        self.order.currentTextChanged.connect(self._on_value_changed)
        self.shape.currentTextChanged.connect(self._on_value_changed)
        self.allow_overlap.stateChanged.connect(self._on_value_changed)
        self._random_button.clicked.connect(self._on_random_clicked)

    @property
    def fov_size(self) -> tuple[float | None, float | None]:
        """Return the FOV size."""
        return self._fov_size

    @fov_size.setter
    def fov_size(self, size: tuple[float | None, float | None]) -> None:
        """Set the FOV size."""
        self._fov_size = size

    # not in the gui for now...

    @property
    def start_at(self) -> int:
        """Return the start_at value."""
        return self._start_at

    @start_at.setter
    def start_at(self, value: int) -> None:
        """Set the start_at value."""
        self._start_at = value
        self._on_value_changed()

    def _on_value_changed(self) -> None:
        """Emit the valueChanged signal."""
        self.valueChanged.emit(self.value())

    def _on_random_clicked(self) -> None:
        # reset the random seed
        self._start_at = 0
        self.random_seed = self._new_seed()
        self.valueChanged.emit(self.value())

    def value(self) -> RandomPoints:
        """Return the values of the widgets."""
        fov_x, fov_y = self._fov_size
        return RandomPoints(
            num_points=self.num_points.value(),
            shape=self.shape.currentText(),
            random_seed=self.random_seed,
            max_width=self.max_width.value(),
            max_height=self.max_height.value(),
            allow_overlap=self.allow_overlap.isChecked(),
            fov_width=fov_x,
            fov_height=fov_y,
            order=self.order.currentText(),
            start_at=self.start_at,
        )

    def setValue(self, value: RandomPoints | Mapping) -> None:
        """Set the values of the widgets."""
        value = RandomPoints.model_validate(value)
        self.random_seed = (
            self._new_seed() if value.random_seed is None else value.random_seed
        )
        self.num_points.setValue(value.num_points)
        self.max_width.setValue(value.max_width)
        self.max_height.setValue(value.max_height)
        self.shape.setCurrentText(value.shape.value)
        self._fov_size = (value.fov_width, value.fov_height)
        self.allow_overlap.setChecked(value.allow_overlap)
        self.start_at = value.start_at  # type: ignore  # until useq is released
        if value.order is not None:  # type: ignore  # until useq is released
            self.order.setCurrentText(value.order.value)  # type: ignore  # until useq is released

    def reset(self) -> None:
        """Reset value to 1 point and 0 area."""
        self.num_points.setValue(1)
        self.max_width.setValue(0)
        self.max_height.setValue(0)
        self.shape.setCurrentText(Shape.ELLIPSE.value)
        self._fov_size = (None, None)

    def _new_seed(self) -> int:
        return random.randint(0, 2**32 - 1)
