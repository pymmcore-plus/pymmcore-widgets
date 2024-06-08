from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

import superqt
import useq
from ndv import DataWrapper, NDViewer
from pymmcore_plus.mda.handlers import TensorStoreHandler
from qtpy.QtWidgets import QFileDialog, QPushButton, QWidget
from superqt.iconify import QIconifyIcon

# this import is necessary so that ndv can find our custom DataWrapper
from . import _data_wrapper  # noqa: F401

if TYPE_CHECKING:
    from pymmcore_plus.mda.handlers._5d_writer_base import _5DWriterBase
    from qtpy.QtWidgets import QWidget


class MDAViewer(NDViewer):
    """StackViewer specialized for pymmcore-plus MDA acquisitions."""

    _data: _5DWriterBase

    def __init__(
        self,
        datastore: _5DWriterBase | TensorStoreHandler | None = None,
        *,
        parent: QWidget | None = None,
    ):
        if datastore is None:
            datastore = TensorStoreHandler()

        # patch the frameReady method to call the superframeReady method
        # AFTER handling the event
        self._superframeReady = getattr(datastore, "frameReady", None)
        if callable(self._superframeReady):
            datastore.frameReady = self._patched_frame_ready  # type: ignore
        else:  # pragma: no cover
            warnings.warn(
                "MDAViewer: datastore does not have a frameReady method to patch, "
                "are you sure this is a valid data handler?",
                stacklevel=2,
            )

        super().__init__(datastore, parent=parent, channel_axis="c")
        self._save_btn = SaveButton(self._data_wrapper)
        self._btns.addWidget(self._save_btn)
        self.dims_sliders.set_locks_visible(True)
        self._channel_names: dict[int, str] = {}

    def _patched_frame_ready(self, *args: Any) -> None:
        self._superframeReady(*args)  # type: ignore
        if len(args) >= 2 and isinstance(e := args[1], useq.MDAEvent):
            self._on_frame_ready(e)

    @superqt.ensure_main_thread  # type: ignore
    def _on_frame_ready(self, event: useq.MDAEvent) -> None:
        c = event.index.get(self._channel_axis)  # type: ignore
        if c not in self._channel_names and c is not None and event.channel:
            self._channel_names[c] = event.channel.config
        self.setIndex(event.index)  # type: ignore

    def _get_channel_name(self, index: Mapping) -> str:
        if self._channel_axis in index:
            if name := self._channel_names.get(index[self._channel_axis]):
                return name
        return super()._get_channel_name(index)


class SaveButton(QPushButton):
    def __init__(
        self,
        data_wrapper: DataWrapper,
        parent: QWidget | None = None,
    ):
        super().__init__(parent=parent)
        self.setIcon(QIconifyIcon("mdi:content-save"))
        self.clicked.connect(self._on_click)

        self._data_wrapper = data_wrapper
        self._last_loc = str(Path.home())

    def _on_click(self) -> None:
        self._last_loc, _ = QFileDialog.getSaveFileName(
            self, "Choose destination", str(self._last_loc), ""
        )
        suffix = Path(self._last_loc).suffix
        if suffix in (".zarr", ".ome.zarr", ""):
            self._data_wrapper.save_as_zarr(self._last_loc)
        else:
            raise ValueError(f"Unsupported file format: {self._last_loc}")
