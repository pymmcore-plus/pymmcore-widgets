from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import useq
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QButtonGroup,
    QGraphicsLineItem,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

from pymmcore_widgets._util import SeparatorWidget
from pymmcore_widgets.useq_widgets.points_plans._grid_row_column_widget import (
    GridRowColumnWidget,
)
from pymmcore_widgets.useq_widgets.points_plans._random_points_widget import (
    RandomPointWidget,
)

if TYPE_CHECKING:
    from useq import WellPlate

FIXED_POLICY = (QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
CENTER = "Center"
RANDOM = "Random"
GRID = "Grid"
OFFSET = 20
RECT = "rectangle"  # Shape.RECTANGLE in useq
ELLIPSE = "ellipse"  # Shape.ELLIPSE in useq

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


class _FOVSelectorWidget(QWidget):
    """Widget to select the FOVVs per well of the plate."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        # centerwidget
        self.center_wdg = RelativePositionWidget()
        self.center_radio_btn = QRadioButton()
        self.center_radio_btn.setChecked(True)
        self.center_radio_btn.setSizePolicy(*FIXED_POLICY)
        self.center_radio_btn.setObjectName(CENTER)
        center_wdg_layout = QHBoxLayout()
        center_wdg_layout.setContentsMargins(0, 0, 0, 0)
        center_wdg_layout.setSpacing(5)
        center_wdg_layout.addWidget(self.center_radio_btn)
        center_wdg_layout.addWidget(self.center_wdg)
        # random widget
        self.random_wdg = RandomPointWidget()
        self.random_wdg.setEnabled(False)
        self.random_radio_btn = QRadioButton()
        self.random_radio_btn.setSizePolicy(*FIXED_POLICY)
        self.random_radio_btn.setObjectName(RANDOM)
        random_wdg_layout = QHBoxLayout()
        random_wdg_layout.setContentsMargins(0, 0, 0, 0)
        random_wdg_layout.setSpacing(5)
        random_wdg_layout.addWidget(self.random_radio_btn)
        random_wdg_layout.addWidget(self.random_wdg)
        # grid widget
        self.grid_wdg = GridRowColumnWidget()
        self.grid_wdg.setEnabled(False)
        self.grid_radio_btn = QRadioButton()
        self.grid_radio_btn.setSizePolicy(*FIXED_POLICY)
        self.grid_radio_btn.setObjectName(GRID)
        grid_wdg_layout = QHBoxLayout()
        grid_wdg_layout.setContentsMargins(0, 0, 0, 0)
        grid_wdg_layout.setSpacing(5)
        grid_wdg_layout.addWidget(self.grid_radio_btn)
        grid_wdg_layout.addWidget(self.grid_wdg)

        # radio buttons group for fov mode selection
        self._mode_btn_group = QButtonGroup()
        self._mode_btn_group.addButton(self.center_radio_btn)
        self._mode_btn_group.addButton(self.random_radio_btn)
        self._mode_btn_group.addButton(self.grid_radio_btn)
        self._mode_btn_group.buttonToggled.connect(self._on_radiobutton_toggled)

        # main
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(SeparatorWidget())
        main_layout.addLayout(center_wdg_layout)
        main_layout.addWidget(SeparatorWidget())
        main_layout.addLayout(random_wdg_layout)
        main_layout.addWidget(SeparatorWidget())
        main_layout.addLayout(grid_wdg_layout)
        main_layout.addWidget(SeparatorWidget())

        # connect
        self.random_wdg.valueChanged.connect(self._on_value_changed)
        self.grid_wdg.valueChanged.connect(self._on_value_changed)

    # _________________________PUBLIC METHODS_________________________ #

    def value(self) -> useq.RelativeMultiPointPlan:
        return self._plate, self._get_mode_widget().value()

    def setValue(
        self, point_plane: useq.RelativeMultiPointPlan, plate: WellPlate | None = None
    ) -> None:
        """Set the value of the widget.

        Parameters
        ----------
        point_plane : RelativeMultiPointPlan | None
            The well plate object.
        mode : Center | useq.RandomPoints | useq.GridRowsColumns
            The mode to use to select the FOVs.
        """
        self._plate = plate

        if self._plate is None:
            # reset view scene and mode widgets
            with signals_blocked(self.random_wdg):
                self.random_wdg.reset()
            with signals_blocked(self.grid_wdg):
                self.grid_wdg.reset()

            # set the radio buttons
            self._update_mode_widgets(mode)
            return

        # update view data
        well_size_x, well_size_y = self._plate.well_size
        view_data = _WellViewData(
            # plate well size in mm, convert to µm
            well_size=(well_size_x * 1000, well_size_y * 1000),
            circular=self._plate.circular_wells,
            padding=OFFSET,
            mode=mode,
        )
        self.well_view.setValue(view_data)

        # update the fov size in each mode widget
        self._update_mode_wdgs_fov_size(
            (mode.fov_width, mode.fov_height) if mode else (None, None)
        )

        self._update_mode_widgets(mode)

    # _________________________PRIVATE METHODS_________________________ #

    def _get_mode_widget(
        self,
    ) -> RelativePositionWidget | RandomPointWidget | GridRowColumnWidget:
        """Return the current mode."""
        if checked_btn := self._mode_btn_group.checkedButton():
            mode_name = checked_btn.objectName()
            if mode_name == CENTER:
                return self.center_wdg
            elif mode_name == RANDOM:
                return self.random_wdg
            elif mode_name == GRID:
                return self.grid_wdg

    def _update_mode_widgets(self, mode: RelativePointPlan | None) -> None:
        """Update the mode widgets."""
        if isinstance(mode, useq.RandomPoints):
            self._set_random_value(mode)
        else:
            # update the randon widget values depending on the plate
            with signals_blocked(self.random_wdg):
                self.random_wdg.setValue(self._plate_to_random(self._plate))
            # update center or grid widgets
            if isinstance(mode, RandomPointWidget):
                self._set_center_value(mode)
            elif isinstance(mode, useq.GridRowsColumns):
                self._set_grid_value(mode)

    def _update_mode_wdgs_fov_size(
        self, fov_size: tuple[float | None, float | None]
    ) -> None:
        """Update the fov size in each mode widget."""
        self.center_wdg.fov_size = fov_size
        self.random_wdg.fov_size = fov_size
        self.grid_wdg.fov_size = fov_size

    def _on_points_warning(self, num_points: int) -> None:
        self.random_wdg._number_of_points.setValue(num_points)

    def _on_radiobutton_toggled(self, radio_btn: QRadioButton) -> None:
        """Update the scene when the tab is changed."""
        self.well_view.clear(_WellAreaGraphicsItem, _FOVGraphicsItem, QGraphicsLineItem)
        self._enable_radio_buttons_wdgs()
        self._update_scene()

        if radio_btn.isChecked():
            self.valueChanged.emit(self.value())

    def _enable_radio_buttons_wdgs(self) -> None:
        """Enable any radio button that is checked."""
        for btn in self._mode_btn_group.buttons():
            self.MODE[btn.objectName()].setEnabled(btn.isChecked())

    def _on_value_changed(
        self, value: useq.RandomPoints | useq.GridRowsColumns
    ) -> None:
        self.well_view.clear(_WellAreaGraphicsItem, _FOVGraphicsItem, QGraphicsLineItem)
        view_data = self.well_view.value().replace(mode=value)
        self.well_view.setValue(view_data)
        self.valueChanged.emit(self.value())

    def _update_scene(self) -> None:
        """Update the scene depending on the selected tab."""
        mode = self._get_mode_widget().value()
        view_data = self.well_view.value().replace(mode=mode)
        self.well_view.setValue(view_data)

    def _set_center_value(self, mode: Center) -> None:
        """Set the center widget values."""
        self.center_radio_btn.setChecked(True)
        self.center_wdg.setValue(mode)

    def _set_random_value(self, mode: useq.RandomPoints) -> None:
        """Set the random widget values."""
        with signals_blocked(self._mode_btn_group):
            self.random_radio_btn.setChecked(True)
            self._enable_radio_buttons_wdgs()

        self._check_for_warnings(mode)
        # here blocking random widget signals to not generate a new random seed
        with signals_blocked(self.random_wdg):
            self.random_wdg.setValue(mode)

    def _set_grid_value(self, mode: useq.GridRowsColumns) -> None:
        """Set the grid widget values."""
        self.grid_radio_btn.setChecked(True)
        self.grid_wdg.setValue(mode)

    def _check_for_warnings(self, mode: useq.RandomPoints) -> None:
        """useq.RandomPoints width and height warning.

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
                "useq.RandomPoints `max_width` and/or `max_height` are larger than "
                "the well size. They will be set to the well size.",
                stacklevel=2,
            )

    def _plate_to_random(self, plate: WellPlate | None) -> useq.RandomPoints:
        """Convert a WellPlate object to a useq.RandomPoints object."""
        well_size_x, well_size_y = plate.well_size if plate is not None else (0.0, 0.0)
        return useq.RandomPoints(
            num_points=self.random_wdg._number_of_points.value(),
            max_width=well_size_x * 1000 if plate else 0.0,  # convert to µm
            max_height=well_size_y * 1000 if plate else 0.0,  # convert to µm
            shape=ELLIPSE if (plate and plate.circular_wells) else RECT,
            random_seed=self.random_wdg.random_seed,
            fov_width=self.random_wdg.fov_size[0],
            fov_height=self.random_wdg.fov_size[1],
        )


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    widget = _FOVSelectorWidget()
    widget.show()
    app.exec_()
