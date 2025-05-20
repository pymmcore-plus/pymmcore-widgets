from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus

from pymmcore_widgets.useq_widgets._grid import GridPlanWidget, Mode

from ._xy_bounds import CoreXYBoundsControl

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget


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
        self._mmc = mmcore or CMMCorePlus.instance()
        self._core_xy_bounds = CoreXYBoundsControl(core=self._mmc)

        super().__init__(parent)

        # replace self._mode_to_widget[Mode.BOUNDS] with self._core_xy_bounds
        self._mode_to_widget[Mode.BOUNDS] = self._core_xy_bounds

        # remove self.bounds_wdg from GridPlanWidget
        self._stack.removeWidget(self.bounds_wdg)
        self.bounds_wdg.hide()
        # add CoreXYBoundsControl widget to GridPlanWidget
        self._stack.addWidget(self._core_xy_bounds)

        self._mmc.events.systemConfigurationLoaded.connect(self._update_fov_size)
        self._mmc.events.pixelSizeChanged.connect(self._update_fov_size)
        self._mmc.events.roiSet.connect(self._update_fov_size)
        self._update_fov_size()

    def _update_fov_size(self) -> None:
        """Update the FOV size in the grid plan widget."""
        if px := self._mmc.getPixelSizeUm():
            self.setFovWidth(self._mmc.getImageWidth() * px)
            self.setFovHeight(self._mmc.getImageHeight() * px)
