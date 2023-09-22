from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus

from pymmcore_widgets.useq_widgets._grid import GridPlanWidget, Mode

from ._xy_bounds import CoreXYBoundsControl

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget


class CoreConnectedGridPlanWidget(GridPlanWidget):
    def __init__(
        self, mmcore: CMMCorePlus | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._mmc = mmcore or CMMCorePlus.instance()

        self._core_xy_bounds = CoreXYBoundsControl(core=self._mmc)
        self._core_xy_bounds.setEnabled(False)
        # replace GridPlanWidget attributes with CoreXYBoundsControl attributes so we
        # can use the same super() methods.
        self.top = self._core_xy_bounds.top_edit
        self.left = self._core_xy_bounds.left_edit
        self.right = self._core_xy_bounds.right_edit
        self.bottom = self._core_xy_bounds.bottom_edit

        # replace the lrtb_wdg from the parent widget with the core_xy_bounds widget
        self.bounds_layout.addWidget(self._core_xy_bounds, 1)
        self.lrtb_wdg.hide()

        # this is required to toggle the enabled/disabled state of our new xy_bounds
        # widget when the radio buttons in the parent widget change.
        self.mode_groups[Mode.BOUNDS] = (
            self._core_xy_bounds,
            self.top,
            self.left,
            self.right,
            self.bottom,
        )

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
