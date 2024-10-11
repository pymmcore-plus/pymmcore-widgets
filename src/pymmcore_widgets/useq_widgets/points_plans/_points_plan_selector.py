from __future__ import annotations

from typing import TYPE_CHECKING

import useq
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

from ._grid_row_column_widget import GridRowColumnWidget
from ._random_points_widget import RandomPointWidget

if TYPE_CHECKING:
    from typing_extensions import TypeAlias

    # excluding useq.GridWidthHeight even though it's also a relative multi point plan
    RelativePointPlan: TypeAlias = (
        useq.GridRowsColumns | useq.RandomPoints | useq.RelativePosition
    )


class RelativePositionWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Single FOV")
        title.setStyleSheet("font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

    def value(self) -> useq.RelativePosition:
        return useq.RelativePosition()

    def setValue(self, plan: useq.RelativePosition) -> None:
        pass


class _FovWidget(QDoubleSpinBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSpecialValueText("--")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setRange(0, 100000)
        self.setValue(200)
        self.setSingleStep(10)


class RelativePointPlanSelector(QWidget):
    """Widget to select a relative multi-position point plan.

    See also: [PointsPlanWidget][pymmcore_widgets.useq_widgets.PointsPlanWidget]
    which combines this widget with a graphical representation of the points.

    In useq, a RelativeMultiPointPlan is one of:
    - useq.RelativePosition
    - useq.RandomPoints
    - useq.GridRowsColumns
    - useq.GridWidthHeight  # not included in this widget
    """

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        # WIDGET ----------------------

        # plan widgets
        self.single_pos_wdg = RelativePositionWidget()
        self.random_points_wdg = RandomPointWidget()
        self.grid_wdg = GridRowColumnWidget()

        # this gets changed when the radio buttons are toggled
        self._active_plan_widget: (
            RelativePositionWidget | RandomPointWidget | GridRowColumnWidget
        ) = self.single_pos_wdg
        self._active_plan_type: type[RelativePointPlan] = useq.RelativePosition

        # radio buttons  selection

        self.single_radio_btn = QRadioButton()
        self.single_radio_btn.setChecked(True)
        self.random_radio_btn = QRadioButton()
        self.grid_radio_btn = QRadioButton()

        self._mode_btn_group = QButtonGroup()
        self._mode_btn_group.addButton(self.single_radio_btn)
        self._mode_btn_group.addButton(self.random_radio_btn)
        self._mode_btn_group.addButton(self.grid_radio_btn)

        self.fov_w = _FovWidget()
        self.fov_h = _FovWidget()

        # CONNECTIONS ----------------------

        self._mode_btn_group.buttonToggled.connect(self._on_radiobutton_toggled)
        self.random_points_wdg.valueChanged.connect(self._on_value_changed)
        self.grid_wdg.valueChanged.connect(self._on_value_changed)
        self.fov_h.valueChanged.connect(self._on_value_changed)
        self.fov_w.valueChanged.connect(self._on_value_changed)

        # LAYOUT ----------------------

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 0, 10, 0)
        for btn, wdg in (
            (self.single_radio_btn, self.single_pos_wdg),
            (self.random_radio_btn, self.random_points_wdg),
            (self.grid_radio_btn, self.grid_wdg),
        ):
            wdg.setEnabled(btn.isChecked())
            grpbx = QGroupBox()
            # make a click on the groupbox act as a click on the button
            grpbx.mousePressEvent = lambda _, b=btn: b.setChecked(True)
            grpbx_layout = QVBoxLayout(grpbx)
            grpbx_layout.setContentsMargins(4, 6, 4, 6)
            grpbx_layout.addWidget(wdg)

            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)
            layout.addWidget(btn, 0)
            layout.addWidget(grpbx, 1)
            main_layout.addLayout(layout, 1)

        # FOV widgets go at the bottom, and are combined into a single widget
        # for ease of showing/hiding the whole thing at once
        self.fov_widgets = QWidget()
        fov_layout = QHBoxLayout(self.fov_widgets)
        fov_layout.setContentsMargins(0, 0, 0, 0)
        fov_layout.setSpacing(2)
        fov_layout.addSpacing(24)
        fov_layout.addWidget(QLabel("FOV (w, h; µm):"))
        fov_layout.addWidget(self.fov_w)
        fov_layout.addWidget(self.fov_h)
        main_layout.addWidget(self.fov_widgets, 0)

    # _________________________PUBLIC METHODS_________________________ #

    @property
    def active_plan_type(self) -> type[RelativePointPlan]:
        return self._active_plan_type

    def value(self) -> useq.RelativeMultiPointPlan:
        # the fov_w/h values are global to all plans
        return self._active_plan_widget.value().model_copy(
            update={
                "fov_width": self.fov_w.value() or None,
                "fov_height": self.fov_h.value() or None,
            }
        )

    def setValue(self, plan: useq.RelativeMultiPointPlan) -> None:
        """Set the value of the widget.

        Parameters
        ----------
        plan : useq.RelativePosition | useq.RandomPoints | useq.GridRowsColumns
            The point plan to set.
        """
        if plan == self.value():
            return

        with signals_blocked(self):
            if isinstance(plan, useq.RandomPoints):
                self.random_points_wdg.setValue(plan)
                self.random_radio_btn.setChecked(True)
            elif isinstance(plan, useq.GridRowsColumns):
                self.grid_wdg.setValue(plan)
                self.grid_radio_btn.setChecked(True)
            elif isinstance(plan, useq.RelativePosition):
                self.single_pos_wdg.setValue(plan)
                self.single_radio_btn.setChecked(True)
            else:  # pragma: no cover
                raise ValueError(f"Invalid plan type: {type(plan)}")
            self.fov_h.setValue(plan.fov_height or 0)
            self.fov_w.setValue(plan.fov_width or 0)
        self._on_value_changed()

    # _________________________PRIVATE METHODS_________________________ #

    def _on_radiobutton_toggled(self, btn: QRadioButton, checked: bool) -> None:
        btn2wdg: dict[QRadioButton, QWidget] = {
            self.single_radio_btn: self.single_pos_wdg,
            self.random_radio_btn: self.random_points_wdg,
            self.grid_radio_btn: self.grid_wdg,
        }
        wdg = btn2wdg[btn]
        wdg.setEnabled(checked)
        if checked:
            self._active_plan_widget = wdg
            self._active_plan_type = {
                self.single_radio_btn: useq.RelativePosition,
                self.random_radio_btn: useq.RandomPoints,
                self.grid_radio_btn: useq.GridRowsColumns,
            }[btn]
            self._on_value_changed()

    def _on_value_changed(self) -> None:
        self.valueChanged.emit(self.value())
