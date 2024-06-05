from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, Mapping

import superqt
import useq
from pymmcore_plus.mda.handlers import TensorStoreHandler

from ._save_button import SaveButton
from ._stack_viewer import StackViewer

if TYPE_CHECKING:
    from pymmcore_plus.mda.handlers._5d_writer_base import _5DWriterBase
    from qtpy.QtWidgets import QWidget


class MDAViewer(StackViewer):
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
