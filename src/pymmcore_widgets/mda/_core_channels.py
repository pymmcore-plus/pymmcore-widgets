from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus

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

        # connections
        self._mmc.events.systemConfigurationLoaded.connect(self._update_channel_groups)
        self._mmc.events.configGroupDeleted.connect(self._update_channel_groups)
        self._mmc.events.configDefined.connect(self._update_channel_groups)

        self._update_channel_groups()

    def _update_channel_groups(self) -> None:
        """Update the channel groups when the system configuration is loaded."""
        gps = self._mmc.getAvailableConfigGroups()
        GROUPS = {group: self._mmc.getAvailableConfigs(group) for group in gps}
        self.setChannelGroups(GROUPS)
