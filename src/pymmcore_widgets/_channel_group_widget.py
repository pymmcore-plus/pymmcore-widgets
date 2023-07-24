from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QComboBox, QWidget
from superqt.utils import signals_blocked


class ChannelGroupWidget(QComboBox):
    """A QComboBox to follow and control Micro-Manager ChannelGroup.

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
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent)

        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._mmc.events.systemConfigurationLoaded.connect(
            self._update_channel_group_combo
        )
        self._mmc.events.configGroupDeleted.connect(self._update_channel_group_combo)
        self._mmc.events.channelGroupChanged.connect(self._on_channel_group_changed)
        self._mmc.events.propertyChanged.connect(self._on_property_changed)
        self._mmc.events.configDefined.connect(self._update_channel_group_combo)

        self.currentTextChanged.connect(self._mmc.setChannelGroup)

        self.destroyed.connect(self._disconnect)

        self._update_channel_group_combo()

    def _update_channel_group_combo(self) -> None:
        with signals_blocked(self):
            self.clear()
            self.addItems(self._mmc.getAvailableConfigGroups())
            self.adjustSize()
            if ch_group := self._mmc.getChannelGroup():
                self.setCurrentText(ch_group)
                self.setStyleSheet("")
            else:
                self.setStyleSheet("color: magenta;")

    def _on_property_changed(self, device: str, property: str, value: str) -> None:
        if device != "Core" or property != "ChannelGroup":
            return
        with signals_blocked(self):
            if value:
                self.setCurrentText(value)
                self.setStyleSheet("")
            else:
                self.setStyleSheet("color: magenta;")

    def _on_channel_group_changed(self, group: str) -> None:
        if group == self.currentText():
            self.setStyleSheet("")
            return
        self._update_channel_group_combo()

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(
            self._update_channel_group_combo
        )
        self._mmc.events.channelGroupChanged.disconnect(self._on_channel_group_changed)
        self._mmc.events.configGroupDeleted.disconnect(self._update_channel_group_combo)
        self._mmc.events.propertyChanged.disconnect(self._on_property_changed)
        self._mmc.events.configDefined.disconnect(self._update_channel_group_combo)
