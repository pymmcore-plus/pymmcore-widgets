from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_widgets.control._load_system_cfg_widget import ConfigurationWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_load_system_cfg_widget(qtbot: QtBot, global_mmcore: CMMCorePlus):
    cfg = ConfigurationWidget()
    qtbot.addWidget(cfg)

    global_mmcore.unloadAllDevices()

    assert len(global_mmcore.getLoadedDevices()) <= 1

    cfg.load_cfg_Button.click()

    assert len(global_mmcore.getLoadedDevices()) > 1
