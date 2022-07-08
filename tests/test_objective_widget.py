from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QDialog

from pymmcore_widgets.objective_widget import ComboMessageBox, ObjectivesWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

# -> to run only if class _ObjectiveStateWidget(StateDeviceWidget) is used


def test_objective_widget_changes_objective(global_mmcore: CMMCorePlus, qtbot: QtBot):
    obj_wdg = ObjectivesWidget()
    qtbot.addWidget(obj_wdg)

    # start_z = 100.0
    # global_mmcore.setPosition("Z", start_z)
    stage_mock = Mock()
    obj_wdg._mmc.events.stagePositionChanged.connect(stage_mock)

    assert obj_wdg._combo.currentText() == "Nikon 10X S Fluor"
    with pytest.raises(ValueError):
        obj_wdg._combo.setCurrentText("10asdfdsX")

    assert global_mmcore.getCurrentPixelSizeConfig() == "Res10x"

    new_val = "Nikon 40X Plan Fluor ELWD"
    with qtbot.waitSignal(global_mmcore.events.propertyChanged):
        obj_wdg._combo.setCurrentText(new_val)

    # stage_mock.assert_has_calls([call("Z", 0), call("Z", start_z)])
    # assert obj_wdg._combo.currentText() == new_val
    # assert global_mmcore.getStateLabel(obj_wdg._objective_device) == new_val
    # assert global_mmcore.getCurrentPixelSizeConfig() == "Res40x"

    # assert global_mmcore.getPosition("Z") == start_z


@patch.object(ComboMessageBox, "exec_")
def test_guess_objectve(dialog_mock, global_mmcore: CMMCorePlus, qtbot: QtBot):
    dialog_mock.return_value = QDialog.DialogCode.Accepted
    with patch.object(global_mmcore, "guessObjectiveDevices") as mock:
        mock.return_value = ["Objective", "Obj2"]
        obj_wdg = ObjectivesWidget(mmcore=global_mmcore)
        qtbot.addWidget(obj_wdg)
