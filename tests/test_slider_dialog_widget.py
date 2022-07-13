from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import QLabel

from pymmcore_widgets._property_widget import PropertyWidget
from pymmcore_widgets._slider_dialog_widget import SliderDialog

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_slider_dialog_widget(qtbot: QtBot, global_mmcore: CMMCorePlus):

    regex = "(test)s?"
    illuminations = SliderDialog(property_regex=regex)
    qtbot.addWidget(illuminations)

    assert illuminations.layout().count() == 10

    for i in range(illuminations.layout().count()):
        wdg = illuminations.layout().itemAt(i).widget()
        if i % 2 == 0:
            assert isinstance(wdg, QLabel)
            assert "Camera::TestProperty" in wdg.text()
        else:
            assert isinstance(wdg, PropertyWidget)
            assert wdg.value() == 0.0
            if i == 5:
                continue
            wdg.setValue(0.1)
            assert wdg.value() == 0.1
