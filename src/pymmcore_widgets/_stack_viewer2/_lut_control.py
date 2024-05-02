from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

import numpy as np
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QCheckBox, QHBoxLayout, QWidget
from superqt import QLabeledRangeSlider
from superqt.cmap import QColormapComboBox
from superqt.utils import signals_blocked

if TYPE_CHECKING:
    import cmap

    from ._protocols import PImageHandle


class LutControl(QWidget):
    def __init__(
        self,
        name: str = "",
        handles: Iterable[PImageHandle] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._handles = handles
        self._name = name

        self._visible = QCheckBox(name)
        self._visible.setChecked(True)
        self._visible.toggled.connect(self._on_visible_changed)

        self._cmap = QColormapComboBox(allow_user_colormaps=True)
        self._cmap.currentColormapChanged.connect(self._on_cmap_changed)
        for handle in handles:
            self._cmap.addColormap(handle.cmap)
        for color in ["green", "magenta", "cyan"]:
            self._cmap.addColormap(color)

        self._clims = QLabeledRangeSlider(Qt.Orientation.Horizontal)
        self._clims.setRange(0, 2**14)
        self._clims.valueChanged.connect(self._on_clims_changed)

        self._auto_clim = QCheckBox("Auto")
        self._auto_clim.toggled.connect(self.update_autoscale)
        self._auto_clim.setChecked(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._visible)
        layout.addWidget(self._cmap)
        layout.addWidget(self._clims)
        layout.addWidget(self._auto_clim)

    def autoscaleChecked(self) -> bool:
        return self._auto_clim.isChecked()

    def _on_clims_changed(self, clims: tuple[float, float]) -> None:
        self._auto_clim.setChecked(False)
        for handle in self._handles:
            handle.clim = clims

    def _on_visible_changed(self, visible: bool) -> None:
        for handle in self._handles:
            handle.visible = visible

    def _on_cmap_changed(self, cmap: cmap.Colormap) -> None:
        for handle in self._handles:
            handle.cmap = cmap

    def update_autoscale(self) -> None:
        if not self._auto_clim.isChecked():
            return

        # find the min and max values for the current channel
        clims = [np.inf, -np.inf]
        for handle in self._handles:
            clims[0] = min(clims[0], np.nanmin(handle.data))
            clims[1] = max(clims[1], np.nanmax(handle.data))

        if (clims_ := tuple(int(x) for x in clims)) != (0, 0):
            for handle in self._handles:
                handle.clim = clims_

        # set the slider values to the new clims
        with signals_blocked(self._clims):
            self._clims.setValue(clims_)
