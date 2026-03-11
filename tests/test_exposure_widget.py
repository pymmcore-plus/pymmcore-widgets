from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pymmcore_widgets import DefaultCameraExposureWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_exposure_widget(qtbot: QtBot, global_mmcore: CMMCorePlus):
    global_mmcore.setExposure(15)
    wdg = DefaultCameraExposureWidget(mmcore=global_mmcore)
    qtbot.addWidget(wdg)

    # check that it get's whatever core is set to.
    assert wdg.spinBox.value() == 15
    global_mmcore.setExposure(30)
    qtbot.waitUntil(lambda: wdg.spinBox.value() == 30)

    wdg.spinBox.setValue(45)
    qtbot.waitUntil(lambda: global_mmcore.getExposure() == 45)

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
    wdg.spinBox.setValue(0.1)
    qtbot.waitUntil(lambda: global_mmcore.getExposure() == 0.1)
