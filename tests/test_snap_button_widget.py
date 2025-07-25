from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import QSize

from pymmcore_widgets.control._snap_button_widget import SnapButton
from tests._utils import wait_signal

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_snap_button_widget(qtbot: QtBot, global_mmcore: CMMCorePlus):
    snap_btn = SnapButton()

    qtbot.addWidget(snap_btn)

    assert snap_btn.text() == "Snap"
    assert snap_btn.iconSize() == QSize(30, 30)

    global_mmcore.startContinuousSequenceAcquisition(0)

    with (
        wait_signal(qtbot, global_mmcore.events.sequenceAcquisitionStopped),
        wait_signal(qtbot, global_mmcore.events.imageSnapped),
    ):
        snap_btn.click()
        assert not global_mmcore.isSequenceRunning()
