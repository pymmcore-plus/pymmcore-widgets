from __future__ import annotations

import useq
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QHBoxLayout, QWidget

from pymmcore_widgets.useq_widgets.points_plans import RelativePointPlanSelector

from ._well_graphics_view import WellView


class FOVSelectorWidget(QWidget):
    """Widget to select the FOVVs per well of the plate."""

    valueChanged = Signal(object)

    def __init__(
        self,
        plan: useq.RelativeMultiPointPlan | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self.selector = RelativePointPlanSelector()
        # graphics scene to draw the well and the fovs
        self.well_view = WellView()

        # main
        layout = QHBoxLayout(self)
        layout.addWidget(self.selector, 1)
        layout.addWidget(self.well_view, 2)

        # connect
        self.selector.valueChanged.connect(self._on_selector_value_changed)
        self.well_view.maxPointsDetected.connect(self._on_view_max_points_detected)
        self.well_view.positionClicked.connect(self._on_view_position_clicked)

        if plan is not None:
            self.setValue(plan)

    def value(self) -> useq.RelativeMultiPointPlan:
        return self.selector.value()

    def setValue(self, plan: useq.RelativeMultiPointPlan) -> None:
        self.selector.setValue(plan)

    def _on_selector_value_changed(self, value: useq.RelativeMultiPointPlan) -> None:
        self.well_view.setPointsPlan(value)
        self.valueChanged.emit(value)

    def _on_view_max_points_detected(self, value: int) -> None:
        self.selector.random_points_wdg.num_points.setValue(value)

    def _on_view_position_clicked(self, position: useq.RelativePosition) -> None:
        if self.selector.active_plan_type is useq.RandomPoints:
            pos_no_name = position.model_copy(update={"name": ""})
            self.selector.random_points_wdg.start_at = pos_no_name
