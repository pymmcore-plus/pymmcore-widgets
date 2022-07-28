from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QCheckBox

from pymmcore_widgets import PresetsWidget
from pymmcore_widgets._group_preset_widget._add_group_widget import AddGroupWidget
from pymmcore_widgets._group_preset_widget._group_preset_table_widget import (
    GroupPresetTableWidget,
)

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


def test_add_group(global_mmcore: CMMCorePlus, qtbot: QtBot):
    gp = GroupPresetTableWidget()
    qtbot.addWidget(gp)
    add_gp_wdg = AddGroupWidget()
    qtbot.addWidget(add_gp_wdg)
    mmc = global_mmcore

    assert "NewGroup" not in mmc.getAvailableConfigGroups()
    groups_in_table = [
        gp.table_wdg.item(r, 0).text() for r in range(gp.table_wdg.rowCount())
    ]
    assert "NewGroup" not in groups_in_table

    table = add_gp_wdg._prop_table

    dev_prop_list = ["Camera-Binning", "Camera-BitDepth", "Camera-CCDTemperature"]

    for idx, i in enumerate(dev_prop_list):
        dev_prop = table.item((idx + 1), 1).text()
        assert dev_prop == i
        cbox = table.cellWidget((idx + 1), 0)
        assert type(cbox) == QCheckBox
        cbox.setChecked(True)
        assert cbox.isChecked()

    add_gp_wdg.group_lineedit.setText("NewGroup")

    add_gp_wdg.new_group_btn.click()

    assert hasattr(add_gp_wdg, "_first_preset_wdg")

    wdg = add_gp_wdg._first_preset_wdg
    assert wdg.preset_name_lineedit.text() == "NewPreset"

    wdg.table.cellWidget(0, 1).setValue(2)
    wdg.table.cellWidget(1, 1).setValue(8)
    wdg.table.cellWidget(2, 1).setValue(0.1)

    with qtbot.waitSignal(mmc.events.newGroupPreset):
        wdg.apply_button.click()

    assert "NewGroup" in mmc.getAvailableConfigGroups()
    groups_in_table = [
        gp.table_wdg.item(r, 0).text() for r in range(gp.table_wdg.rowCount())
    ]
    assert "NewGroup" in groups_in_table

    dev_prop_val = [
        (k[0], k[1], k[2]) for k in mmc.getConfigData("NewGroup", "NewPreset")
    ]

    assert [
        ("Camera", "Binning", "2"),
        ("Camera", "BitDepth", "8"),
        ("Camera", "CCDTemperature", "0.1"),
    ] == dev_prop_val


def test_edit_group(global_mmcore: CMMCorePlus, qtbot: QtBot):
    pass


def test_delete_group(global_mmcore: CMMCorePlus, qtbot: QtBot):
    gp = GroupPresetTableWidget()
    qtbot.addWidget(gp)
    mmc = global_mmcore

    assert "Camera" in mmc.getAvailableConfigGroups()

    for r in range(gp.table_wdg.rowCount()):

        group_name = gp.table_wdg.item(r, 0).text()

        if group_name == "Camera":

            with qtbot.waitSignal(mmc.events.groupDeleted):
                mmc.deleteConfigGroup("Camera")
            break

    assert "Camera" not in mmc.getAvailableConfigGroups()
    groups_in_table = [
        gp.table_wdg.item(r, 0).text() for r in range(gp.table_wdg.rowCount())
    ]
    assert "Camera" not in groups_in_table


def test_add_preset(global_mmcore: CMMCorePlus, qtbot: QtBot):
    pass


def test_edit_preset(global_mmcore: CMMCorePlus, qtbot: QtBot):
    pass


def test_delete_preset(global_mmcore: CMMCorePlus, qtbot: QtBot):
    gp = GroupPresetTableWidget()
    qtbot.addWidget(gp)
    mmc = global_mmcore

    assert "Camera" in mmc.getAvailableConfigGroups()
    assert ["HighRes", "LowRes", "MedRes"] == list(mmc.getAvailableConfigs("Camera"))

    camera_group_row = 0
    for r in range(gp.table_wdg.rowCount()):

        group_name = gp.table_wdg.item(r, 0).text()
        wdg = cast(PresetsWidget, gp.table_wdg.cellWidget(r, 1))

        if group_name == "Camera":
            camera_group_row = r
            assert wdg.allowedValues() == mmc.getAvailableConfigs("Camera")
            break

    with qtbot.waitSignal(mmc.events.presetDeleted):
        mmc.deleteConfig("Camera", "LowRes")

    assert "LowRes" not in mmc.getAvailableConfigs("Camera")
    wdg = cast(PresetsWidget, gp.table_wdg.cellWidget(camera_group_row, 1))
    assert "LowRes" not in wdg.allowedValues()
