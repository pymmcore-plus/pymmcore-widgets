from __future__ import annotations

from typing import Union

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QPushButton, QSizePolicy, QWidget
from superqt.fonticon import icon
from superqt.utils import create_worker

COLOR_TYPES = Union[
    QColor,
    int,
    str,
    Qt.GlobalColor,
    "tuple[int, int, int, int]",
    "tuple[int, int, int]",
]


class SnapButton(QPushButton):
    """Create a snap QPushButton.

    This button is linked to the
    [`CMMCorePlus.snap`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.snap] method.
    Once the button is clicked, an image is acquired and the `pymmcore-plus`
    signal [`imageSnapped`]() is emitted.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].

    Examples
    --------
    !!! example "Combining `SnapButton` with other widgets"

        see [ImagePreview](../ImagePreview#example)
    """

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )

        self._mmc = mmcore or CMMCorePlus.instance()

        self._mmc.events.systemConfigurationLoaded.connect(self._on_system_cfg_loaded)
        self._on_system_cfg_loaded()
        self.destroyed.connect(self._disconnect)

        self._create_button()

        self.setEnabled(False)
        if len(self._mmc.getLoadedDevices()) > 1:
            self.setEnabled(True)

    def _create_button(self) -> None:
        self.setText("Snap")
        self.setIcon(icon(MDI6.camera_outline, color=(0, 255, 0)))
        self.setIconSize(QSize(30, 30))
        self.clicked.connect(self._snap)

    def _snap(self) -> None:
        if self._mmc.isSequenceRunning():
            self._mmc.stopSequenceAcquisition()

        def snap_with_shutter() -> None:
            """
            Perform a snap and ensure shutter signals are sent.

            This is necessary as not all shutter devices properly
            send signals as they are opened and closed.
            """
            autoshutter = self._mmc.getAutoShutter()
            if autoshutter:
                self._mmc.events.propertyChanged.emit(
                    self._mmc.getShutterDevice(), "State", True
                )
            self._mmc.snap()
            if autoshutter:
                self._mmc.events.propertyChanged.emit(
                    self._mmc.getShutterDevice(), "State", False
                )

        create_worker(snap_with_shutter, _start_thread=True)

    def _on_system_cfg_loaded(self) -> None:
        self.setEnabled(bool(self._mmc.getCameraDevice()))

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(
            self._on_system_cfg_loaded
        )
