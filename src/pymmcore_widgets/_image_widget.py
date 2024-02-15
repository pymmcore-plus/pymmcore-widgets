from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import QVBoxLayout, QWidget

if TYPE_CHECKING:
    from typing import Literal

    import numpy as np

_DEFAULT_WAIT = 10


class ImagePreview(QWidget):
    """A Widget that displays the last image snapped by active core.

    This widget will automatically update when the active core snaps an image, when the
    active core starts streaming or when a Multi-Dimensional Acquisition is running.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget. By default, None.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    use_with_mda: bool
        If False, the widget will not update when a Multi-Dimensional Acquisition is
        running. By default, True.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
        use_with_mda: bool = True,
    ):
        try:
            from vispy import scene
        except ImportError as e:
            raise ImportError(
                "vispy is required for ImagePreview. "
                "Please run `pip install pymmcore-widgets[image]`"
            ) from e

        super().__init__(parent=parent)
        self._mmc = mmcore or CMMCorePlus.instance()
        self._use_with_mda = use_with_mda
        self._imcls = scene.visuals.Image
        self._clims: tuple[float, float] | Literal["auto"] = "auto"
        self._cmap: str = "grays"

        self._canvas = scene.SceneCanvas(
            keys="interactive", size=(512, 512), parent=self
        )
        self.view = self._canvas.central_widget.add_view(camera="panzoom")
        self.view.camera.aspect = 1

        self.streaming_timer = QTimer(parent=self)
        self.streaming_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.streaming_timer.setInterval(int(self._mmc.getExposure()) or _DEFAULT_WAIT)
        self.streaming_timer.timeout.connect(self._on_streaming_timeout)

        ev = self._mmc.events
        ev.imageSnapped.connect(self._on_image_snapped)
        ev.continuousSequenceAcquisitionStarted.connect(self._on_streaming_start)
        ev.sequenceAcquisitionStopped.connect(self._on_streaming_stop)
        ev.exposureChanged.connect(self._on_exposure_changed)

        self.image: scene.visuals.Image | None = None
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self._canvas.native)

        self.destroyed.connect(self._disconnect)

    @property
    def use_with_mda(self) -> bool:
        """Get whether the widget should update when a MDA is running."""
        return self._use_with_mda

    @use_with_mda.setter
    def use_with_mda(self, use_with_mda: bool) -> None:
        """Set whether the widget should update when a MDA is running.

        Parameters
        ----------
        use_with_mda : bool
            Whether the widget is used with MDA.
        """
        self._use_with_mda = use_with_mda

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

    def _on_streaming_timeout(self) -> None:
        with suppress(RuntimeError, IndexError):
            self._update_image(self._mmc.getLastImage())

    def _on_image_snapped(self) -> None:
        if self._mmc.mda.is_running() and not self._use_with_mda:
            return
        self._update_image(self._mmc.getImage())

    def _update_image(self, img: np.ndarray) -> None:
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
    def clims(self) -> tuple[float, float] | Literal["auto"]:
        """Get the contrast limits of the image."""
        return self._clims

    @clims.setter
    def clims(self, clims: tuple[float, float] | Literal["auto"] = "auto") -> None:
        """Set the contrast limits of the image.

        Parameters
        ----------
        clims : tuple[float, float], or "auto"
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
