from typing import cast

import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (
    QGridLayout,
    QLayout,
    QRadioButton,
    QWidget,
)

from pymmcore_widgets.useq_widgets import GridPlanWidget

from ._xy_bounds import CoreXYBoundsControl


class CoreConnectedGridPlanWidget(GridPlanWidget):
    def __init__(
        self, mmcore: CMMCorePlus | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._mmc = mmcore or CMMCorePlus.instance()

        _layout = cast(QLayout, self.layout().itemAt(4))
        # hide the widgets we don't need from the GridPlanWidget's GridFromEdges plan
        self._edges_radiobtn: QRadioButton | None = None
        self._hide_widgets(_layout)
        # replace them with the CoreXYBoundsControl
        _grid_layout = cast(QGridLayout, _layout.itemAt(1))
        _grid_layout.setContentsMargins(0, 0, 0, 0)
        self._core_xy_bounds = CoreXYBoundsControl(core=self._mmc)
        self._core_xy_bounds.setEnabled(False)
        _grid_layout.addWidget(self._core_xy_bounds, 0, 0, 1, 4)

        # replace GridPlanWidget attributes with CoreXYBoundsControl attributes so we
        # can use the same super() methods.
        self.top = self._core_xy_bounds.top_edit._spin
        self.left = self._core_xy_bounds.left_edit._spin
        self.right = self._core_xy_bounds.right_edit._spin
        self.bottom = self._core_xy_bounds.bottom_edit._spin

        # connect
        self.top.valueChanged.connect(self._on_change)
        self.left.valueChanged.connect(self._on_change)
        self.right.valueChanged.connect(self._on_change)
        self.bottom.valueChanged.connect(self._on_change)

    def _hide_widgets(self, layout: QLayout) -> None:
        """Recursively hide all widgets in the GridPlanWidget GridFromEdges layout."""
        for i in range(layout.count()):
            item = layout.itemAt(i)
            wdg = item.widget()
            if wdg is not None:
                if isinstance(wdg, QRadioButton):
                    self._edges_radiobtn = wdg
                    self._edges_radiobtn.toggled.connect(self._on_toggle)
                    continue
                wdg.hide()
            else:
                self._hide_widgets(item)

    def _on_toggle(self, checked: bool) -> None:
        self._core_xy_bounds.setEnabled(checked)

    def _on_change(self) -> None:
        # TODO: owerriding this for now because there is some issue in the rendering of
        # the GridFromEdges. Will work on it in the future

        val = self.value()

        if val is None:
            return

        if isinstance(val, useq.GridRowsColumns):
            draw_grid = val.replace(relative_to="top_left")
            draw_grid.fov_height = 1 / ((val.rows - 1) or 1)
            draw_grid.fov_width = 1 / ((val.columns - 1) or 1)
            self._grid_img.grid = draw_grid
        else:
            # TODO: draw also GridWidthHeight and GridFromEdges
            self._grid_img.grid = None

        self._grid_img.update()

        self.valueChanged.emit(val)

    def value(self) -> useq.GridFromEdges | useq.GridRowsColumns | useq.GridWidthHeight:
        value = super().value()
        if isinstance(value, useq.GridWidthHeight):
            # convert from mm to um
            value = value.replace(width=value.width * 1000, height=value.height * 1000)

        return value
