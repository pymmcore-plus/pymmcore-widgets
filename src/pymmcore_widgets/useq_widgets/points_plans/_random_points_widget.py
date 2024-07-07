from __future__ import annotations

import numpy as np
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from useq import RandomPoints
from useq._grid import Shape

AlignCenter = Qt.AlignmentFlag.AlignCenter
EXPANDING_W = (QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
RECT = Shape.RECTANGLE
ELLIPSE = Shape.ELLIPSE


class RandomPointWidget(QGroupBox):
    """Widget to generate random points within a specified area."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # setting a random seed for point generation reproducibility
        self._random_seed: int = int(np.random.randint(0, 2**32 - 1, dtype=np.uint32))
        self._is_circular: bool = False
        self._fov_size: tuple[float | None, float | None] = (None, None)

        # title
        title = QLabel(text="Random Fields of Views.")
        title.setStyleSheet("font-weight: bold;")
        title.setAlignment(AlignCenter)
        # well area doublespinbox along x
        self._area_x = QDoubleSpinBox()
        self._area_x.setAlignment(AlignCenter)
        self._area_x.setSizePolicy(*EXPANDING_W)
        self._area_x.setMinimum(0.0)
        self._area_x.setMaximum(1000000)
        self._area_x.setSingleStep(100)
        # well area doublespinbox along y
        self._area_y = QDoubleSpinBox()
        self._area_y.setAlignment(AlignCenter)
        self._area_y.setSizePolicy(*EXPANDING_W)
        self._area_y.setMinimum(0.0)
        self._area_y.setMaximum(1000000)
        self._area_y.setSingleStep(100)
        # number of FOVs spinbox
        self._number_of_points = QSpinBox()
        self._number_of_points.setAlignment(AlignCenter)
        self._number_of_points.setSizePolicy(*EXPANDING_W)
        self._number_of_points.setMinimum(1)
        self._number_of_points.setMaximum(1000)
        # form layout
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        form_layout.setSpacing(5)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.addRow(QLabel("Area x (µm):"), self._area_x)
        form_layout.addRow(QLabel("Area y (µm):"), self._area_y)
        form_layout.addRow(QLabel("Points:"), self._number_of_points)
        # random button
        self._random_button = QPushButton(text="Generate Random Points")

        # main
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(title)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self._random_button)

        # connect
        self._area_x.valueChanged.connect(self._on_value_changed)
        self._area_y.valueChanged.connect(self._on_value_changed)
        self._number_of_points.valueChanged.connect(self._on_value_changed)
        self._random_button.clicked.connect(self._on_random_clicked)

    @property
    def is_circular(self) -> bool:
        """Return True if the well is circular."""
        return self._is_circular

    @is_circular.setter
    def is_circular(self, circular: bool) -> None:
        """Set True if the well is circular."""
        self._is_circular = circular

    @property
    def fov_size(self) -> tuple[float | None, float | None]:
        """Return the FOV size."""
        return self._fov_size

    @fov_size.setter
    def fov_size(self, size: tuple[float | None, float | None]) -> None:
        """Set the FOV size."""
        self._fov_size = size

    @property
    def random_seed(self) -> int:
        """Return the random seed."""
        return self._random_seed

    @random_seed.setter
    def random_seed(self, seed: int) -> None:
        """Set the random seed."""
        self._random_seed = seed

    def _on_value_changed(self) -> None:
        """Emit the valueChanged signal."""
        self.valueChanged.emit(self.value())

    def _on_random_clicked(self) -> None:
        """Emit the valueChanged signal."""
        # reset the random seed
        self.random_seed = int(np.random.randint(0, 2**32 - 1, dtype=np.uint32))
        self.valueChanged.emit(self.value())

    def value(self) -> RandomPoints:
        """Return the values of the widgets."""
        fov_x, fov_y = self._fov_size
        return RandomPoints(
            num_points=self._number_of_points.value(),
            shape=ELLIPSE if self._is_circular else RECT,
            random_seed=self.random_seed,
            max_width=self._area_x.value(),
            max_height=self._area_y.value(),
            allow_overlap=False,
            fov_width=fov_x,
            fov_height=fov_y,
        )

    def setValue(self, value: RandomPoints) -> None:
        """Set the values of the widgets."""
        self.is_circular = value.shape == ELLIPSE
        self.random_seed = (
            value.random_seed
            if value.random_seed is not None
            else int(np.random.randint(0, 2**32 - 1, dtype=np.uint32))
        )
        self._number_of_points.setValue(value.num_points)
        self._area_x.setMaximum(value.max_width)
        self._area_x.setValue(value.max_width)
        self._area_y.setMaximum(value.max_height)
        self._area_y.setValue(value.max_height)
        self._fov_size = (value.fov_width, value.fov_height)

    def reset(self) -> None:
        """Reset the values of the widgets."""
        self._number_of_points.setValue(1)
        self._area_x.setValue(0)
        self._area_y.setValue(0)
        self._fov_size = (None, None)
        self.is_circular = False
