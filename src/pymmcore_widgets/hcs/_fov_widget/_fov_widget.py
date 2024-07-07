from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QHBoxLayout,
    QWidget,
)

from pymmcore_widgets.hcs._fov_widget._fov_sub_widgets import WellView
from pymmcore_widgets.useq_widgets.points_plans import RelativePointPlanSelector

if TYPE_CHECKING:
    import useq
    from useq import (
        RandomPoints,
    )

    pass


class FOVSelectorWidget(QWidget):
    """Widget to select the FOVVs per well of the plate."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        self.selector = RelativePointPlanSelector()
        # graphics scene to draw the well and the fovs
        self.well_view = WellView()

        # main
        layout = QHBoxLayout(self)
        layout.addWidget(self.selector)
        layout.addWidget(self.well_view)

        # connect
        self.selector.valueChanged.connect(self._on_selector_value_changed)
        self.well_view.pointsWarning.connect(self._on_points_warning)

        # self.setValue(self._plate, mode)

    # _________________________PUBLIC METHODS_________________________ #

    def value(self) -> useq.RelativeMultiPointPlan:
        return self.selector.value()

    def setValue(self, plan: useq.RelativeMultiPointPlan) -> None:
        self.selector.setValue()

    def _on_selector_value_changed(self, value: useq.RelativeMultiPointPlan) -> None:
        self.well_view.setValue(view_data)
        self.valueChanged.emit(value)

    # _________________________PRIVATE METHODS_________________________ #

    def _on_points_warning(self, num_points: int) -> None:
        self.random_wdg._number_of_points.setValue(num_points)

    def _update_scene(self) -> None:
        """Update the scene depending on the selected tab."""
        view_data = self.well_view.value().replace(mode=self.value())
        self.well_view.setValue(view_data)

    def _check_for_warnings(self, mode: RandomPoints) -> None:
        """RandomPoints width and height warning.

        If max width and height are grater than the plate well size, set them to the
        plate well size.
        """
        if self._plate is None:
            return

        # well_size is in mm, convert to µm
        well_size_x, well_size_y = self._plate.well_size
        if mode.max_width > well_size_x * 1000 or mode.max_height > well_size_y * 1000:
            mode = mode.replace(
                max_width=well_size_x * 1000,
                max_height=well_size_y * 1000,
            )
            warnings.warn(
                "RandomPoints `max_width` and/or `max_height` are larger than "
                "the well size. They will be set to the well size.",
                stacklevel=2,
            )
