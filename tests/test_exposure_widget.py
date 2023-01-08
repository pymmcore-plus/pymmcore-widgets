from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pymmcore_plus import CMMCorePlus

from pymmcore_widgets import DefaultCameraExposureWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_exposure_widget(qtbot: QtBot, global_mmcore: CMMCorePlus):
    global_mmcore.setExposure(15)
    wdg = DefaultCameraExposureWidget(mmcore=global_mmcore)
    qtbot.addWidget(wdg)

    # check that it get's whatever core is set to.
    assert wdg.spinBox.value() == 15
    with qtbot.waitSignal(global_mmcore.events.exposureChanged):
        global_mmcore.setExposure(30)
    assert wdg.spinBox.value() == 30

    with qtbot.wait_signal(global_mmcore.events.exposureChanged):
        wdg.spinBox.setValue(45)
    assert global_mmcore.getExposure() == 45

    # test updating cameraDevice
    global_mmcore.setProperty("Core", "Camera", "")
    assert not wdg.isEnabled()

    with pytest.raises(RuntimeError):
        wdg.setCamera("blarg")

    # set to an invalid camera name
    # should now be disabled.
    wdg.setCamera("blarg", force=True)
    assert not wdg.isEnabled()

    # reset the camera to a working one
    global_mmcore.setProperty("Core", "Camera", "Camera")
    with qtbot.wait_signal(global_mmcore.events.exposureChanged):
        wdg.spinBox.setValue(12)
    assert global_mmcore.getExposure() == 12
