from __future__ import annotations

import useq
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

from pymmcore_widgets._util import SeparatorWidget

from ._grid_row_column_widget import GridRowColumnWidget
from ._random_points_widget import RandomPointWidget

# excluding useq.GridWidthHeight even though it's also a valid relative multi point plan
RelativePointPlan = useq.GridRowsColumns | useq.RandomPoints | useq.RelativePosition


class RelativePositionWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Single FOV"))

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
        self.relative_pos_wdg = RelativePositionWidget()
        self.random_points_wdg = RandomPointWidget()
        self.grid_wdg = GridRowColumnWidget()
        # this gets changed when the radio buttons are toggled
        self._active_plan_widget: (
            RelativePositionWidget | RandomPointWidget | GridRowColumnWidget
        ) = self.relative_pos_wdg

        # radio buttons  selection

        self.center_radio_btn = QRadioButton()
        self.center_radio_btn.setChecked(True)
        self.random_radio_btn = QRadioButton()
        self.grid_radio_btn = QRadioButton()

        self._mode_btn_group = QButtonGroup()
        self._mode_btn_group.addButton(self.center_radio_btn)
        self._mode_btn_group.addButton(self.random_radio_btn)
        self._mode_btn_group.addButton(self.grid_radio_btn)

        # CONNECTIONS ----------------------

        self._mode_btn_group.buttonToggled.connect(self._on_radiobutton_toggled)
        self.random_points_wdg.valueChanged.connect(self._on_value_changed)
        self.grid_wdg.valueChanged.connect(self._on_value_changed)

        # LAYOUT ----------------------

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        for btn, wdg in (
            (self.center_radio_btn, self.relative_pos_wdg),
            (self.random_radio_btn, self.random_points_wdg),
            (self.grid_radio_btn, self.grid_wdg),
        ):
            wdg.setEnabled(btn.isChecked())
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)
            layout.addWidget(btn, 0)
            layout.addWidget(wdg, 1)
            main_layout.addLayout(layout)

        for i in range(0, 7, 2):
            main_layout.insertWidget(i, SeparatorWidget())

    # _________________________PUBLIC METHODS_________________________ #

    def value(self) -> useq.RelativeMultiPointPlan:
        return self._active_plan_widget.value()

    def setValue(self, plan: useq.RelativeMultiPointPlan) -> None:
        """Set the value of the widget.

        Parameters
        ----------
        plan : useq.RelativePosition | useq.RandomPoints | useq.GridRowsColumns
            The point plan to set.
        """
        if isinstance(plan, useq.RandomPoints):
            with signals_blocked(self.random_points_wdg):
                self.random_points_wdg.setValue(plan)
            self.random_radio_btn.setChecked(True)
        elif isinstance(plan, useq.GridRowsColumns):
            with signals_blocked(self.grid_wdg):
                self.grid_wdg.setValue(plan)
            self.grid_radio_btn.setChecked(True)
        elif isinstance(plan, useq.RelativePosition):
            with signals_blocked(self.relative_pos_wdg):
                self.relative_pos_wdg.setValue(plan)
            self.center_radio_btn.setChecked(True)
        raise ValueError(f"Invalid plan type: {type(plan)}")

    # _________________________PRIVATE METHODS_________________________ #

    def _on_radiobutton_toggled(self, btn: QRadioButton, checked: bool) -> None:
        btn2wdg: dict[QRadioButton, QWidget] = {
            self.center_radio_btn: self.relative_pos_wdg,
            self.random_radio_btn: self.random_points_wdg,
            self.grid_radio_btn: self.grid_wdg,
        }
        wdg = btn2wdg[btn]
        wdg.setEnabled(checked)
        if checked:
            self._active_plan_widget = wdg
            self.valueChanged.emit(self.value())

    def _on_value_changed(self) -> None:
        self.valueChanged.emit(self.value())
