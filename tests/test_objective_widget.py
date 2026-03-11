from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, call, patch

import pytest
from qtpy.QtWidgets import QDialog

from pymmcore_widgets._util import ComboMessageBox
from pymmcore_widgets.control._objective_widget import ObjectivesWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_objective_widget_changes_objective(global_mmcore: CMMCorePlus, qtbot: QtBot):
    obj_wdg = ObjectivesWidget()
    qtbot.addWidget(obj_wdg)

    start_z = 100.0
    global_mmcore.setPosition("Z", start_z)

    px_size_mock = Mock()
    obj_wdg._mmc.events.pixelSizeChanged.connect(px_size_mock)

    assert obj_wdg._combo.currentText() == "Nikon 10X S Fluor"
    with pytest.raises(ValueError):
        obj_wdg._combo.setCurrentText("10asdfdsX")

    assert global_mmcore.getCurrentPixelSizeConfig() == "Res10x"

    new_val = "Nikon 40X Plan Fluor ELWD"

    # Track setPosition calls synchronously via wrapping instead of relying on
    # stagePositionChanged signals, which are emitted from short-lived C++
    # background threads and suffer unreliable cross-thread Qt event delivery.
    with patch.object(
        global_mmcore, "setPosition", wraps=global_mmcore.setPosition
    ) as sp_mock:
        obj_wdg._combo.setCurrentText(new_val)

    # The hooks call setPosition synchronously: Z drops to 0, then restores.
    sp_mock.assert_has_calls([call("Z", 0), call("Z", start_z)])

    # pixelSizeChanged is emitted synchronously from the main thread
    px_size_mock.assert_has_calls([call(0.25)])

    qtbot.waitUntil(lambda: obj_wdg._combo.currentText() == new_val)
    assert global_mmcore.getStateLabel(obj_wdg._objective_device) == new_val
    assert global_mmcore.getCurrentPixelSizeConfig() == "Res40x"
    assert global_mmcore.getPosition("Z") == start_z


@patch.object(ComboMessageBox, "exec")
def test_guess_objectve(dialog_mock, global_mmcore: CMMCorePlus, qtbot: QtBot):
    dialog_mock.return_value = QDialog.DialogCode.Accepted
    with patch.object(global_mmcore, "guessObjectiveDevices") as mock:
        mock.return_value = ["Objective", "Obj2"]
        obj_wdg = ObjectivesWidget(mmcore=global_mmcore)
        qtbot.addWidget(obj_wdg)
