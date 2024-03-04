from __future__ import annotations

from pymmcore import g_Keyword_CoreCamera, g_Keyword_CoreDevice
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QDoubleSpinBox, QHBoxLayout, QLabel, QWidget
from superqt.utils import signals_blocked


class ExposureWidget(QWidget):
    """A Widget to get/set exposure on a camera.

    Parameters
    ----------
    camera : str
        The camera device label. By default, None. If not specified,
        the widget will use the current Camera device.
    parent : QWidget | None
        Optional parent widget. By default, None.
    mmcore : CMMCorePlus | None
        Optional `CMMCorePlus` micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new) `CMMCorePlus.instance()`.

    Examples
    --------
    !!! example "Combining `ExposureWidget` with other widgets"

        see [ImagePreview](ImagePreview.md#example)

    """

    def __init__(
        self,
        camera: str | None = None,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ):
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._camera = camera or self._mmc.getCameraDevice()

        self.label = QLabel()
        self.label.setText(" ms")
        self.label.setMaximumWidth(30)
        self.spinBox = QDoubleSpinBox()
        self.spinBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinBox.setMinimum(0.001)
        self.spinBox.setMaximum(999999.0)
        self.spinBox.setKeyboardTracking(False)
        layout = QHBoxLayout()
        layout.addWidget(self.spinBox)
        layout.addWidget(self.label)
        self.setLayout(layout)

        self._on_load()
        self._mmc.events.exposureChanged.connect(self._on_exp_changed)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_load)

        self.spinBox.valueChanged.connect(self._mmc.setExposure)

        self.destroyed.connect(self._disconnect)

    def _disconnect(self) -> None:
        self._mmc.events.exposureChanged.disconnect(self._on_exp_changed)
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_load)

    def setCamera(self, camera: str | None = None) -> None:
        """Set which camera this widget tracks.

        Parameters
        ----------
        camera : str
            The camera device label. By default, None. If not specified,
            the widget will use the current Camera device.
        """
        orig_cam = self._camera
        self._camera = camera or self._mmc.getCameraDevice()
        if orig_cam != self._camera:
            self._on_load()

    def _on_load(self) -> None:
        with signals_blocked(self.spinBox):
            if self._camera and self._camera in self._mmc.getLoadedDevices():
                self.setEnabled(True)
                self.spinBox.setValue(self._mmc.getExposure(self._camera))
            else:
                self.setEnabled(False)

    def _on_exp_changed(self, camera: str, exposure: float) -> None:
        if camera == self._camera:
            with signals_blocked(self.spinBox):
                self.spinBox.setValue(exposure)

    def _on_exp_set(self, exposure: float) -> None:
        self._mmc.setExposure(self._camera, exposure)


class DefaultCameraExposureWidget(ExposureWidget):
    """A Widget to get/set exposure on the default camera.

    Parameters
    ----------
    parent : QWidget | None
            Optional parent widget. By default, None.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ):
        super().__init__(parent=parent, mmcore=mmcore)

        self._mmc.events.devicePropertyChanged(
            g_Keyword_CoreDevice, g_Keyword_CoreCamera
        ).connect(self._camera_updated)

        self.destroyed.connect(self._disconnect)

    def _disconnect(self) -> None:
        self._mmc.events.exposureChanged.disconnect(self._on_exp_changed)
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_load)
        self._mmc.events.devicePropertyChanged(
            g_Keyword_CoreDevice, g_Keyword_CoreCamera
        ).disconnect(self._camera_updated)

    def setCamera(self, camera: str | None = None, force: bool = False) -> None:
        """Set which camera this widget tracks.

        Using this on the ``DefaultCameraExposureWidget``widget may cause unexpected
        behavior, instead try to use an ``ExposureWidget``.

        Parameters
        ----------
        camera : str
            The camera device label. By default, None. If not specified,
            the widget will use the current Camera device.
        force : bool
            Whether to force a change away from tracking the default camera.
        """
        if not force:
            raise RuntimeError(
                "Setting the camera on a DefaultCameraExposureWidget "
                "may cause it to malfunction. Either use *force=True* "
                " or create an ExposureWidget"
            )
        return super().setCamera(camera)

    def _camera_updated(self, value: str) -> None:
        # This will not always fire
        # see https://github.com/micro-manager/mmCoreAndDevices/issues/181
        self._camera = value
        # this will result in a double call of _on_load if this callback
        # was triggered by a configuration load. But I don't see an easy way around that
        # fortunately _on_load should be low cost
        self._on_load()


if __name__ == "__main__":  # pragma: no cover
    import sys

    CMMCorePlus.instance().loadSystemConfiguration()
    app = QApplication(sys.argv)
    win = DefaultCameraExposureWidget()
    win.show()
    sys.exit(app.exec_())
