from typing import Optional, Tuple, Union

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
    Tuple[int, int, int, int],
    Tuple[int, int, int],
]


class SnapButton(QPushButton):
    """Create a snap QPushButton linked to the pymmcore-plus 'snap()' method.

    Once the button is clicked, an image is acquired and the pymmcore-plus
    'imageSnapped(image: nparray)' signal is emitted.
    """

    def __init__(
        self,
        *,
        parent: Optional[QWidget] = None,
        mmcore: Optional[CMMCorePlus] = None,
    ) -> None:

        super().__init__(parent)

        self.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed))

        self._mmc = mmcore or CMMCorePlus.instance()
        self._camera = self._mmc.getCameraDevice()

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
        if self._mmc.isSequenceRunning(self._camera):
            self._mmc.stopSequenceAcquisition(self._camera)
        if self._mmc.getAutoShutter():
            self._mmc.events.propertyChanged.emit(
                self._mmc.getShutterDevice(), "State", True
            )
        create_worker(self._mmc.snap, _start_thread=True)

    def _on_system_cfg_loaded(self) -> None:
        self._camera = self._mmc.getCameraDevice()
        self.setEnabled(bool(self._camera))

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(
            self._on_system_cfg_loaded
        )
