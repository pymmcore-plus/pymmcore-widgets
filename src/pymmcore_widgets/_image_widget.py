from typing import TYPE_CHECKING, Optional

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QVBoxLayout, QWidget

if TYPE_CHECKING:
    import numpy as np


class ImagePreview(QWidget):
    """Widget that displays the last image snapped by core.

    This widget will automatically update when the core snaps an image or when
    the core starts streaming.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        try:
            from vispy import scene
        except ImportError as e:
            raise ImportError(
                "vispy is required for ImagePreview. Please run `pip install pymmcore-widgets[image]`"
            ) from e

        super().__init__(parent)
        self._mmc = CMMCorePlus.instance()
        self._imcls = scene.visuals.Image

        self.streaming_timer = QTimer()
        self.streaming_timer.setInterval(int(self._mmc.getExposure()) or 10)
        self.streaming_timer.timeout.connect(self._on_image_snapped)

        self._connect()

        self._canvas = scene.SceneCanvas(keys="interactive", show=True, size=(512, 512))
        self.view = self._canvas.central_widget.add_view(camera="panzoom")
        self.view.camera.aspect = 1

        self.image = None
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self._canvas.native)

    def _connect(self) -> None:
        ev = self._mmc.events
        ev.imageSnapped.connect(self._on_image_snapped)
        ev.startContinuousSequenceAcquisition.connect(self._on_streaming_start)
        ev.stopSequenceAcquisition.connect(self._on_streaming_stop)
        ev.exposureChanged.connect(self._on_exposure_changed)

    def _disconnect(self) -> None:
        ev = self._mmc.events
        ev.imageSnapped.disconnect(self._on_image_snapped)
        ev.startContinuousSequenceAcquisition.disconnect(self._on_streaming_start)
        ev.stopSequenceAcquisition.disconnect(self._on_streaming_stop)
        ev.exposureChanged.disconnect(self._on_exposure_changed)

    def _on_streaming_start(self) -> None:
        self.streaming_timer.start()

    def _on_streaming_stop(self) -> None:
        self.streaming_timer.stop()

    def _on_exposure_changed(self, device: str, value: str) -> None:
        self.streaming_timer.setInterval(int(value))

    def _on_image_snapped(self, img: Optional["np.ndarray"] = None) -> None:
        if img is None:
            try:
                img = self._mmc.getLastImage()
            except (RuntimeError, IndexError):
                return

        clim = (img.min(), img.max())
        if self.image is None:
            self.image = self._imcls(
                img, cmap="grays", clim=clim, parent=self.view.scene
            )
            self.view.camera.set_range(margin=0)
        else:
            self.image.set_data(img)
            self.image.clim = clim


if __name__ == "__main__":
    # example
    from qtpy.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget

    from pymmcore_widgets._live_button_widget import LiveButton
    from pymmcore_widgets._snap_button_widget import SnapButton

    core = CMMCorePlus.instance()
    core.loadSystemConfiguration()
    app = QApplication([])

    btns = QWidget()
    btns.setLayout(QHBoxLayout())
    btns.layout().addWidget(LiveButton())
    btns.layout().addWidget(SnapButton())

    main = QWidget()
    main.setLayout(QVBoxLayout())
    main.layout().addWidget(ImagePreview())
    main.layout().addWidget(btns)
    main.show()

    app.exec_()
