from __future__ import annotations

import useq
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QHBoxLayout, QWidget

from pymmcore_widgets.useq_widgets.points_plans import RelativePointPlanSelector

from ._well_graphics_view import WellView

INIT_PLAN = useq.RandomPoints(
    num_points=10,
    max_width=4000,
    max_height=4000,
    fov_width=400,
    fov_height=340,
    shape="ellipse",
    allow_overlap=False,
)
INIT_WELL_SIZE = 6


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
    well_size : tuple[float, float] | float | None
        The size of the well in mm. If a tuple, the first element is the width and the
        second element is the height. If a float, the width and height are the same.
        By default, None.
    parent : QWidget | None
        The parent widget.
    """

    valueChanged = Signal(object)

    def __init__(
        self,
        plan: useq.RelativeMultiPointPlan | None = None,
        well_size: tuple[float, float] | float | None = None,
        is_well_circular: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent=parent)

        wdt: float | None
        hgt: float | None
        if isinstance(well_size, tuple):
            wdt, hgt = well_size
        elif isinstance(well_size, (int, float)) or well_size is None:
            wdt = hgt = well_size
        self._well_width_µm: float | None = wdt * 1000 if wdt is not None else None
        self._well_height_µm: float | None = hgt * 1000 if hgt is not None else None

        self._is_well_circular = is_well_circular

        self._selector = RelativePointPlanSelector()
        # graphics scene to draw the well and the fovs
        self._well_view = WellView(self._is_well_circular)

        # main
        layout = QHBoxLayout(self)
        layout.addWidget(self._selector, 1)
        layout.addWidget(self._well_view, 2)

        # connect
        self._selector.valueChanged.connect(self._on_selector_value_changed)
        self._well_view.maxPointsDetected.connect(self._on_view_max_points_detected)
        self._well_view.positionClicked.connect(self._on_view_position_clicked)

        # if plan is not None:
        self.setValue(plan or INIT_PLAN)

        # init the view with the current well size
        self.setWellSize(wdt or INIT_WELL_SIZE, hgt or INIT_WELL_SIZE)

    def value(self) -> useq.RelativeMultiPointPlan:
        """Return the selected plan."""
        return self._selector.value()

    def setValue(self, plan: useq.RelativeMultiPointPlan) -> None:
        """Set the current plan."""
        self._selector.setValue(plan)

    def wellSize(self) -> tuple[float | None, float | None]:
        """Return the well size in mm."""
        w = self._well_width_µm / 1000 if self._well_width_µm is not None else None
        h = self._well_height_µm / 1000 if self._well_height_µm is not None else None
        return w, h

    def setWellSize(
        self, width: float | None = None, height: float | None = None
    ) -> None:
        """Set the well size.

        Parameters
        ----------
        width : float | None
            The width of the well in mm. By default, None.
        height : float | None
            The height of the well in mm. By default, None.
        """
        # update the well size in the well view
        self._well_view.setWellSize(width, height)
        # update the max width and height of the random points widget
        w = width * 1000 if width is not None else 1000000  # 1000000 is the default
        h = height * 1000 if height is not None else 1000000  # 1000000 is the default
        self._selector.random_points_wdg.max_width.setMaximum(w)
        self._selector.random_points_wdg.max_height.setMaximum(h)
        # update the visual items in view if the current plan is a random points plan
        if self._selector.active_plan_type is useq.RandomPoints:
            self._on_selector_value_changed(self.value())

    def circularWell(self) -> bool:
        """Return True if the well is circular, False otherwise."""
        return self._is_well_circular

    def setCircularWell(self, circular: bool) -> None:
        """Set the shape of the well."""
        self._well_view.setCircularWell(circular)
        self._on_selector_value_changed(self.value())

    def _on_selector_value_changed(self, value: useq.RelativeMultiPointPlan) -> None:
        self._well_view.setPointsPlan(value)
        self.valueChanged.emit(value)

    def _on_view_max_points_detected(self, value: int) -> None:
        self._selector.random_points_wdg.num_points.setValue(value)

    def _on_view_position_clicked(self, position: useq.RelativePosition) -> None:
        if self._selector.active_plan_type is useq.RandomPoints:
            pos_no_name = position.model_copy(update={"name": ""})
            self._selector.random_points_wdg.start_at = pos_no_name
