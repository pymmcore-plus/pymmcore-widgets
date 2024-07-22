from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QHBoxLayout, QWidget

from pymmcore_widgets.useq_widgets._grid import GridPlanWidget

from ._xy_bounds import CoreXYBoundsControl


class CoreConnectedGridPlanWidget(GridPlanWidget):
    """[GridPlanWidget](../GridPlanWidget#) connected to a Micro-Manager core instance.

    Parameters
    ----------
    mmcore : CMMCorePlus | None
        Optional [`CMMCorePlus`][pymmcore_plus.CMMCorePlus] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    parent : QWidget | None
        Optional parent widget, by default None.
    """

    def __init__(
        self, mmcore: CMMCorePlus | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._mmc = mmcore or CMMCorePlus.instance()

        self._core_xy_bounds = CoreXYBoundsControl(core=self._mmc)
        # replace GridPlanWidget attributes with CoreXYBoundsControl attributes so we
        # can use the same super() methods.
        self.top = self._core_xy_bounds.top_edit
        self.left = self._core_xy_bounds.left_edit
        self.right = self._core_xy_bounds.right_edit
        self.bottom = self._core_xy_bounds.bottom_edit

        # replace the lrtb_wdg from the parent widget with the core_xy_bounds widget
        # self.bounds_wdg.bounds_layout.removeWidget(self.bounds_wdg.lrtb_wdg)
        # self.bounds_wdg.lrtb_wdg.hide()

        for wdg in self.bounds_wdg.children():
            if isinstance(wdg, QWidget):
                wdg.setParent(self)
                wdg.hide()
        QWidget().setLayout(self.bounds_wdg.layout())

        new_layout = QHBoxLayout()
        new_layout.addWidget(self._core_xy_bounds)
        self.bounds_wdg.setLayout(new_layout)
        # self.bounds_wdg.layout().addWidget(self._core_xy_bounds)

        # connect
        self.top.valueChanged.connect(self._on_change)
        self.left.valueChanged.connect(self._on_change)
        self.right.valueChanged.connect(self._on_change)
        self.bottom.valueChanged.connect(self._on_change)

        self._mmc.events.systemConfigurationLoaded.connect(self._update_fov_size)
        self._mmc.events.pixelSizeChanged.connect(self._update_fov_size)
        self._update_fov_size()

    def _update_fov_size(self) -> None:
        """Update the FOV size in the grid plan widget."""
        if px := self._mmc.getPixelSizeUm():
            self.setFovWidth(self._mmc.getImageWidth() * px)
            self.setFovHeight(self._mmc.getImageHeight() * px)
