from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple, Union

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QVBoxLayout, QWidget

if TYPE_CHECKING:
    from typing import Literal

    import numpy as np


class ImagePreview(QWidget):
    """A Widget that displays the last image snapped by active core.

    This widget will automatically update when the active core snaps an image
    or when the active core starts streaming.

    Parameters
    ----------
    parent : Optional[QWidget]
        Optional parent widget. By default, None.
    mmcore: Optional[CMMCorePlus]
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance][].
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        mmcore: Optional[CMMCorePlus] = None,
    ):
        try:
            from vispy import scene
        except ImportError as e:
            raise ImportError(
                "vispy is required for ImagePreview. "
                "Please run `pip install pymmcore-widgets[image]`"
            ) from e

        super().__init__(parent)
        self._mmc = mmcore or CMMCorePlus.instance()
        self._imcls = scene.visuals.Image
        self._clims: Union[Tuple[float, float], Literal["auto"]] = "auto"
        self._cmap: str = "grays"

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
        ev.continuousSequenceAcquisitionStarted.connect(self._on_streaming_start)
        ev.sequenceAcquisitionStopped.connect(self._on_streaming_stop)
        ev.exposureChanged.connect(self._on_exposure_changed)

    def _disconnect(self) -> None:
        ev = self._mmc.events
        ev.imageSnapped.disconnect(self._on_image_snapped)
        ev.continuousSequenceAcquisitionStarted.disconnect(self._on_streaming_start)
        ev.sequenceAcquisitionStopped.disconnect(self._on_streaming_stop)
        ev.exposureChanged.disconnect(self._on_exposure_changed)

    def _on_streaming_start(self) -> None:
        self.streaming_timer.start()

    def _on_streaming_stop(self) -> None:
        self.streaming_timer.stop()

    def _on_exposure_changed(self, device: str, value: str) -> None:
        self.streaming_timer.setInterval(int(value))

    def _on_image_snapped(self, img: Optional[np.ndarray] = None) -> None:
        if img is None:
            try:
                img = self._mmc.getLastImage()
            except (RuntimeError, IndexError):
                return

        clim = (img.min(), img.max()) if self._clims == "auto" else self._clims
        if self.image is None:
            self.image = self._imcls(
                img, cmap=self._cmap, clim=clim, parent=self.view.scene
            )
            self.view.camera.set_range(margin=0)
        else:
            self.image.set_data(img)
            self.image.clim = clim

    @property
    def clims(self) -> Union[Tuple[float, float], Literal["auto"]]:
        """Get the contrast limits of the image."""
        return self._clims

    @clims.setter
    def clims(
        self, clims: Union[Tuple[float, float], Literal["auto"]] = "auto"
    ) -> None:
        """Set the contrast limits of the image.

        Parameters
        ----------
        clims : Tuple[float, float], or "auto"
            The contrast limits to set.
        """
        if self.image is not None:
            self.image.clim = clims
        self._clims = clims

    @property
    def cmap(self) -> str:
        """Get the colormap (lookup table) of the image."""
        return self._cmap

    @cmap.setter
    def cmap(self, cmap: str = "grays") -> None:
        """Set the colormap (lookup table) of the image.

        Parameters
        ----------
        cmap : str
            The colormap to use.
        """
        if self.image is not None:
            self.image.cmap = cmap
        self._cmap = cmap
