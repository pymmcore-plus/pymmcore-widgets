from __future__ import annotations

import useq
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QHBoxLayout, QWidget

from pymmcore_widgets.useq_widgets.points_plans import RelativePointPlanSelector

from ._well_graphics_view import WellView


class PointsPlanWidget(QWidget):
    """Widget to select the FOVVs per well of the plate.

    This widget allows the user to select the number of FOVs per well, (or to generally
    show a multi-point plan, such as a grid or random points plan, even if not within
    the context of a well plate.)

    The value() method returns the selected plan, one of:
        - [useq.GridRowsColumns][]
        - [useq.RandomPoints][]
        - [useq.RelativePosition][]

    Parameters
    ----------
    plan : useq.RelativeMultiPointPlan | None
        The useq MultiPoint plan to display and edit.
    parent : QWidget | None
        The parent widget.
    """

    valueChanged = Signal(object)

    def __init__(
        self,
        plan: useq.RelativeMultiPointPlan | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._selector = RelativePointPlanSelector()
        # graphics scene to draw the well and the fovs
        self._well_view = WellView()

        # main
        layout = QHBoxLayout(self)
        layout.addWidget(self._selector, 1)
        layout.addWidget(self._well_view, 2)

        # connect
        self._selector.valueChanged.connect(self._on_selector_value_changed)
        self._well_view.maxPointsDetected.connect(self._on_view_max_points_detected)
        self._well_view.positionClicked.connect(self._on_view_position_clicked)
        self._well_view.wellSizeSet.connect(self._on_view_well_size_set)

        if plan is not None:
            self.setValue(plan)

        # init the view with the current well size
        self._init_well_size()

    def value(self) -> useq.RelativeMultiPointPlan:
        return self._selector.value()

    def setValue(self, plan: useq.RelativeMultiPointPlan) -> None:
        self._selector.setValue(plan)

    def setWellSize(self, width: float | None, height: float | None) -> None:
        self._well_view.setWellSize(width, height)

    def _on_selector_value_changed(self, value: useq.RelativeMultiPointPlan) -> None:
        self._well_view.setPointsPlan(value)
        self.valueChanged.emit(value)

    def _on_view_max_points_detected(self, value: int) -> None:
        self._selector.random_points_wdg.num_points.setValue(value)

    def _on_view_position_clicked(self, position: useq.RelativePosition) -> None:
        if self._selector.active_plan_type is useq.RandomPoints:
            pos_no_name = position.model_copy(update={"name": ""})
            self._selector.random_points_wdg.start_at = pos_no_name

    def _on_view_well_size_set(self, width: float | None, height: float | None) -> None:
        """Set the max width and height of the random points widget and update the view.

        Note: width and height are in mm.
        """
        w = width * 1000 if width is not None else 1000000  # 1000000 is the default
        h = height * 1000 if height is not None else 1000000  # 1000000 is the default
        self._selector.random_points_wdg.max_width.setMaximum(w)
        self._selector.random_points_wdg.max_height.setMaximum(h)
        # update the view
        self._on_selector_value_changed(self.value())

    def _init_well_size(self) -> None:
        """Initialize the widget with by setting the current well size."""
        # this will make sure that if the well size exists, the random points max width
        # and max height are set to the well size
        w = self._well_view._well_width_um
        h = self._well_view._well_height_um
        w = w / 1000 if w is not None else None  # convert to mm
        h = h / 1000 if h is not None else None  # convert to mm
        self._on_view_well_size_set(w, h)
