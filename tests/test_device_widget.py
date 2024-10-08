from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pymmcore_plus import CMMCorePlus, DeviceType

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_state_device_widget(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    from pymmcore_widgets import DeviceWidget, StateDeviceWidget

    for label in global_mmcore.getLoadedDevicesOfType(DeviceType.StateDevice):
        wdg: StateDeviceWidget = DeviceWidget.for_device(label)
        qtbot.addWidget(wdg)
        wdg.show()
        assert wdg.deviceLabel() == label
        # assert wdg.deviceName() == "DObjective"
        assert global_mmcore.getStateLabel(label) == wdg._combo.currentText()
        assert global_mmcore.getState(label) == wdg._combo.currentIndex()
        start_state = wdg.state()

        next_state = (wdg.state() + 1) % len(wdg.stateLabels())
        with qtbot.waitSignal(global_mmcore.events.propertyChanged):
            global_mmcore.setState(label, next_state)

        assert wdg.state() != start_state
        assert wdg.state() == global_mmcore.getState(label) == wdg._combo.currentIndex()
        assert (
            wdg.stateLabel()
            == global_mmcore.getStateLabel(label)
            == wdg._combo.currentText()
        )

        wdg._disconnect()
        # once disconnected, core changes shouldn't call out to the widget
        global_mmcore.setState(label, start_state)
        assert global_mmcore.getStateLabel(label) != wdg._combo.currentText()
