from __future__ import annotations

from typing import TYPE_CHECKING

import useq
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QButtonGroup,
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


class RelativePointPlanSelector(QWidget):
    """Widget to select a relative multi-position point plan.

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

        # CONNECTIONS ----------------------

        self._mode_btn_group.buttonToggled.connect(self._on_radiobutton_toggled)
        self.random_points_wdg.valueChanged.connect(self._on_value_changed)
        self.grid_wdg.valueChanged.connect(self._on_value_changed)

        # LAYOUT ----------------------

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 0, 10, 0)
        for btn, wdg in (
            (self.single_radio_btn, self.single_pos_wdg),
            (self.random_radio_btn, self.random_points_wdg),
            (self.grid_radio_btn, self.grid_wdg),
        ):
            wdg.setEnabled(btn.isChecked())  # type: ignore [attr-defined]
            grpbx = QGroupBox()
            # make a click on the groupbox act as a click on the button
            grpbx.mousePressEvent = lambda _, b=btn: b.setChecked(True)
            grpbx.setLayout(QVBoxLayout())
            grpbx.layout().addWidget(wdg)

            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)
            layout.addWidget(btn, 0)
            layout.addWidget(grpbx, 1)
            main_layout.addLayout(layout)

        # for i in range(1, 5, 2):
        # main_layout.insertWidget(i, SeparatorWidget())

    # _________________________PUBLIC METHODS_________________________ #

    @property
    def active_plan_type(self) -> type[RelativePointPlan]:
        return self._active_plan_type

    def value(self) -> useq.RelativeMultiPointPlan:
        return self._active_plan_widget.value()

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
