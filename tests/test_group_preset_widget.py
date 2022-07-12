from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus

from pymmcore_widgets._group_preset_table_widget import GroupPresetTableWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_populating_group_preset_table(global_mmcore: CMMCorePlus, qtbot: QtBot):
    gp = GroupPresetTableWidget()
    qtbot.addWidget(gp)

    assert len(list(global_mmcore.getAvailableConfigGroups())) == 9

    for r in range(gp.table_wdg.rowCount()):

        group_name = gp.table_wdg.item(r, 0).text()
        wdg = gp.table_wdg.cellWidget(r, 1)

        if group_name == "Channel":
            assert set(wdg.allowedValues()) == {"DAPI", "FITC", "Cy5", "Rhodamine"}
            wdg.setValue("FITC")
            assert global_mmcore.getCurrentConfig(group_name) == "FITC"

            global_mmcore.setConfig("Channel", "DAPI")
            assert wdg.value() == "DAPI"

        elif group_name == "_combobox_no_preset_test":
            assert set(wdg.allowedValues()) == {
                "8",
                "16",
                "10",
                "32",
                "14",
                "12",
            }
            wdg.setValue("8")
            assert global_mmcore.getProperty("Camera", "BitDepth") == "8"

        elif group_name == "_lineedit_test":
            assert str(wdg.value()) in {"512", "512.0"}
            wdg.setValue("256")
            assert global_mmcore.getProperty("Camera", "OnCameraCCDXSize") == "256"

        elif group_name == "_slider_test":
            assert type(wdg.value()) == float
            wdg.setValue(0.1)
            assert global_mmcore.getProperty("Camera", "TestProperty1") == "0.1000"
