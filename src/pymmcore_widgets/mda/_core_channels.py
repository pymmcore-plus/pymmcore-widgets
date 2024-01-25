from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pymmcore_plus import CMMCorePlus
from superqt.utils import signals_blocked

from pymmcore_widgets.useq_widgets import ChannelTable

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

DEFAULT_EXP = 100.0


class CoreConnectedChannelTable(ChannelTable):
    """[ChannelTable](../ChannelTable#) connected to a Micro-Manager core instance.

    Parameters
    ----------
    rows : int
        Number of rows to initialize the table with, by default 0.
    mmcore : CMMCorePlus | None
        Optional [`CMMCorePlus`][pymmcore_plus.CMMCorePlus] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    parent : QWidget | None
        Optional parent widget, by default None.
    """

    def __init__(
        self,
        rows: int = 0,
        mmcore: CMMCorePlus | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(rows, parent)
        self._mmc = mmcore or CMMCorePlus.instance()

        # when a new row is inserted, call _on_rows_inserted
        # to update the new values from the core channels
        self.table().model().rowsInserted.connect(self._on_rows_inserted)

    def _add_row(self) -> None:
        """Add a new to the end of the table and use the current core position."""
        # note: _add_row is only called when act_add_row is triggered
        # (e.g. when the + button is clicked). Not when a row is added programmatically

        # block the signal that's going to be emitted until _on_rows_inserted
        # has had a chance to update the values from the current channels
        with signals_blocked(self):
            super()._add_row()
        self.valueChanged.emit()

    def _on_rows_inserted(self, parent: Any, start: int, end: int) -> None:
        # when a new row is inserted by any means, populate it
        # this is connected above in __init_ with self.model().rowsInserted.connect
        with signals_blocked(self):
            for row_idx in range(start, end + 1):
                self._set_channel_group_from_core(row_idx)
        self.valueChanged.emit()

    def _set_channel_group_from_core(self, row: int, col: int = 0) -> None:
        """Set the current core channel group at the given row."""
        if not self._mmc.getChannelGroup():
            return

        data = {
            self.GROUP.key: self._mmc.getChannelGroup(),
        }
        self.table().setRowData(row, data)
