from typing import Optional, Tuple, Union

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QPushButton, QSizePolicy, QWidget
from superqt.fonticon import icon
from superqt.utils import create_worker

from ._core import get_core_singleton

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

    Properties
    ----------
    button_text: str
        Text of the QPushButton.
        Default = "Snap".
    icon_size: int
        Size of the QPushButton icon.
        Default = 30.
    icon_color: COLOR_TYPE
       Color of the QPushButton icon in the on and off state.
       Default = (0, 255, 0)
    """

    def __init__(
        self,
        *,
        parent: Optional[QWidget] = None,
        mmcore: Optional[CMMCorePlus] = None,
    ) -> None:

        super().__init__(parent)

        self.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed))

        self._mmc = mmcore or get_core_singleton()
        self._camera = self._mmc.getCameraDevice()
        self._button_text: str = "Snap"
        self._icon_size: int = 30
        self._icon_color: COLOR_TYPES = (0, 255, 0)

        self._mmc.events.systemConfigurationLoaded.connect(self._on_system_cfg_loaded)
        self._on_system_cfg_loaded()
        self.destroyed.connect(self._disconnect)

        self._create_button()

        self.setEnabled(False)
        if len(self._mmc.getLoadedDevices()) > 1:
            self.setEnabled(True)

    @property
    def button_text(self) -> str:
        """Set the text of the snap button."""
        return self._button_text

    @button_text.setter
    def button_text(self, text: str) -> None:
        self.setText(text)
        self._button_text = text

    @property
    def icon_size(self) -> int:
        """Set the snap button icon size."""
        return self._icon_size

    @icon_size.setter
    def icon_size(self, size: int) -> None:
        self.setIconSize(QSize(size, size))
        self._icon_size = size

    @property
    def icon_color(self) -> COLOR_TYPES:
        """Set the snap button icon color."""
        return self._icon_color

    @icon_color.setter
    def icon_color(self, color: COLOR_TYPES) -> None:
        self.setIcon(icon(MDI6.camera_outline, color=color))
        self._icon_color = color

    def _create_button(self) -> None:
        self.setText(self._button_text)
        self.setIcon(icon(MDI6.camera_outline, color=self._icon_color))
        self.setIconSize(QSize(self._icon_size, self._icon_size))
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
