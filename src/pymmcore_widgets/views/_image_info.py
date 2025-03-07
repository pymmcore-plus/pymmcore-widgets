from __future__ import annotations

from contextlib import suppress

import numpy as np
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QWidget, QComboBox

_DEFAULT_WAIT = 10


class ImageInfo(QWidget):
    """A Widget that displays information about the last image by active core.

    This widget will automatically update when the active core snaps an image, when the
    active core starts streaming or when a Multi-Dimensional Acquisition is running.

    Heavily based/stolen from `pymmcore_widgets.ImagePreview`.

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

    # image_updated = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
        use_with_mda: bool = True,
    ):
        try:
            import pyqtgraph as pg
        except ImportError as e:
            raise ImportError(
                "pyqtgraph is required for ImageInfo. "
                "Please run `pip install pymmcore-widgets[plot]`"
            ) from e

        super().__init__(parent=parent)
        self._mmc = mmcore or CMMCorePlus.instance()
        self._use_with_mda = use_with_mda

        self._min: float | None = None
        self._max: float | None = None
        self._std: float | None = None
        self._clims: tuple[float, float] | Literal["auto"] = "auto"

        self.streaming_timer = QTimer(parent=self)
        self.streaming_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.streaming_timer.setInterval(int(self._mmc.getExposure()) or _DEFAULT_WAIT)
        self.streaming_timer.timeout.connect(self._on_streaming_timeout)

        # info label ---
        self.info_label = QLabel(
            f"Min: {self._min}, Max: {self._max}, Std: {self._std}"
        )
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)


        # histogram plot ---
        self._histogram_widget = pg.PlotWidget(background=None)
        self._histogram_widget.setXRange(0, 255)  # Set the x-limits here
        self._histogram_widget.setLabel("left", "Frequency")
        self._histogram_widget.setLabel("bottom", "Pixel Value")
        self._histogram_plot = self._histogram_widget.plot(
            stepMode=True, fillLevel=0, brush=(0, 0, 255, 80)
        )

        # options
        self._range_selector = QComboBox()
        self._range_selector.addItems(["auto", "8-bit (0-255)", "10-bit (0-1023)", "12-bit (0-4095)", "16-bit (0-65535)"])
        self._range_selector.setCurrentText("auto")

        # layout
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self._histogram_widget)

        self._bottom_layout = QHBoxLayout()
        self._bottom_layout.addWidget(self.info_label)
        self._bottom_layout.addWidget(self._range_selector)

        self.layout().addLayout(self._bottom_layout)

        # connect to events
        ev = self._mmc.events
        ev.imageSnapped.connect(self._on_image_snapped)
        ev.continuousSequenceAcquisitionStarted.connect(self._on_streaming_start)
        ev.sequenceAcquisitionStopped.connect(self._on_streaming_stop)
        ev.exposureChanged.connect(self._on_exposure_changed)

        self._range_selector.currentIndexChanged.connect(self._on_dropdown_changed)
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
        self._min, self._max = img.min(), img.max()
        self._std = img.std()
        self.info_label.setText(
            f"Min: {self._min}, Max: {self._max}, Std: {self._std:.1f}"
        )

        y, x = np.histogram(img.flatten())
        self._histogram_plot.setData(x, y)
        self._update_range()

    def _on_dropdown_changed(self):
        self._update_range()

    def _update_range(self):
        selected_option = self._range_selector.currentIndex()

        if selected_option == 0:
            # auto
            self._clims = "auto"
            self._histogram_widget.setXRange(self._min, self._max)
        elif selected_option == 1:
            # 8-bit
            self._histogram_widget.setXRange(0, 255)
        elif selected_option == 2:
            # 10-bit
            self._histogram_widget.setXRange(0, 1023)
        elif selected_option == 3:
            # 12-bit
            self._histogram_widget.setXRange(0, 4095)
        elif selected_option == 4:
            # 16-bit
            self._histogram_widget.setXRange(0, 65535)