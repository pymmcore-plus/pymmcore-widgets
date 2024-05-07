from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

import superqt
import useq

from ._save_button import SaveButton
from ._stack_viewer import StackViewer

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget


class MDAViewer(StackViewer):
    """StackViewer specialized for pymmcore-plus MDA acquisitions."""

    def __init__(self, datastore: Any = None, *, parent: QWidget | None = None):
        if datastore is None:
            from pymmcore_plus.mda.handlers import OMEZarrWriter

            datastore = OMEZarrWriter()

        # patch the frameReady method to call the superframeReady method
        # AFTER handling the event
        self._superframeReady = getattr(datastore, "frameReady", None)
        if callable(self._superframeReady):
            datastore.frameReady = self._patched_frame_ready
        else:  # pragma: no cover
            warnings.warn(
                "MDAViewer: datastore does not have a frameReady method to patch, "
                "are you sure this is a valid data handler?",
                stacklevel=2,
            )

        super().__init__(datastore, parent=parent, channel_axis="c")
        self._save_btn = SaveButton(self.data)
        self._btns.addWidget(self._save_btn)
        self.dims_sliders.set_locks_visible(True)

    def _patched_frame_ready(self, *args: Any) -> None:
        self._superframeReady(*args)  # type: ignore
        if len(args) >= 2 and isinstance(e := args[1], useq.MDAEvent):
            self._on_frame_ready(e)

    @superqt.ensure_main_thread  # type: ignore
    def _on_frame_ready(self, event: useq.MDAEvent) -> None:
        self.setIndex(event.index)  # type: ignore
