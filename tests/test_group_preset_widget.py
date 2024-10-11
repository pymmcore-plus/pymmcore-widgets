from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pytest
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QFileDialog

from pymmcore_widgets import PresetsWidget
from pymmcore_widgets.config_presets._group_preset_widget import (
    AddGroupWidget,
    AddPresetWidget,
    EditGroupWidget,
    EditPresetWidget,
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
            assert isinstance(wdg.value(), float)
            wdg.setValue(0.1)
            assert global_mmcore.getProperty("Camera", "TestProperty1") == "0.1000"


def test_add_group(qtbot: QtBot):
    gp = GroupPresetTableWidget()
    qtbot.addWidget(gp)
    add_gp_wdg = AddGroupWidget()
    qtbot.addWidget(add_gp_wdg)
    mmc = CMMCorePlus.instance()

    assert "NewGroup" not in mmc.getAvailableConfigGroups()
    groups_in_table = [
        gp.table_wdg.item(r, 0).text() for r in range(gp.table_wdg.rowCount())
    ]
    assert "NewGroup" not in groups_in_table

    table = add_gp_wdg._prop_table

    dev_prop_list = ["Camera-Binning", "Camera-BitDepth", "Camera-CCDTemperature"]

    bin_match = table.findItems("Camera-Binning", Qt.MatchFlag.MatchExactly)
    bit_match = table.findItems("Camera-BitDepth", Qt.MatchFlag.MatchExactly)
    t_match = table.findItems("Camera-CCDTemperature", Qt.MatchFlag.MatchExactly)

    rows = [bin_match[0].row(), bit_match[0].row(), t_match[0].row()]

    for idx, i in enumerate(dev_prop_list):
        item = table.item(rows[idx], 0)
        assert item.text() == i
        item.setCheckState(Qt.CheckState.Checked)

    assert table.getCheckedProperties() == [
        ("Camera", "Binning", "1"),
        ("Camera", "BitDepth", "16"),
        ("Camera", "CCDTemperature", "0.0"),
    ]

    with pytest.warns(UserWarning):
        add_gp_wdg.new_group_btn.click()
        assert add_gp_wdg.info_lbl.text() == "Give a name to the group!"

        add_gp_wdg.group_lineedit.setText("Camera")
        add_gp_wdg.new_group_btn.click()
        assert add_gp_wdg.info_lbl.text() == "'Camera' already exist!"

    add_gp_wdg.group_lineedit.setText("NewGroup")

    add_gp_wdg.new_group_btn.click()
    wdg = add_gp_wdg._first_preset_wdg
    assert wdg.table.item(0, 0).text() == "Camera-Binning"
    assert wdg.table.item(1, 0).text() == "Camera-BitDepth"

    assert wdg.preset_name_lineedit.placeholderText() == "NewPreset"

    wdg.table.cellWidget(0, 1).setValue(2)
    wdg.table.cellWidget(1, 1).setValue(8)
    wdg.table.cellWidget(2, 1).setValue("0.1")

    with qtbot.waitSignal(mmc.events.configDefined):
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
    edit_gp = EditGroupWidget("Camera")
    qtbot.addWidget(edit_gp)
    mmc = global_mmcore

    table = edit_gp._prop_table

    bin_match = table.findItems("Camera-Binning", Qt.MatchFlag.MatchExactly)
    bin_row = bin_match[0].row()
    bit_match = table.findItems("Camera-BitDepth", Qt.MatchFlag.MatchExactly)
    bit_row = bit_match[0].row()

    assert table.item(bin_row, 0).text() == "Camera-Binning"
    assert table.item(bit_row, 0).text() == "Camera-BitDepth"

    edit_gp.modify_group_btn.click()
    assert edit_gp.info_lbl.text() == ""

    t_match = table.findItems("Camera-CCDTemperature", Qt.MatchFlag.MatchExactly)
    t_row = t_match[0].row()

    item = table.item(t_row, 0)
    assert item.checkState() != Qt.CheckState.Checked
    item.setCheckState(Qt.CheckState.Checked)
    assert table.item(t_row, 0).text() == "Camera-CCDTemperature"

    edit_gp.group_lineedit.setText("Camera_New")

    edit_gp.modify_group_btn.click()
    assert edit_gp.info_lbl.text() == "'Camera_New' Group Modified."

    assert "Camera" not in mmc.getAvailableConfigGroups()
    assert "Camera_New" in mmc.getAvailableConfigGroups()

    dp = [k[:2] for k in mmc.getConfigData("Camera_New", "LowRes")]
    assert ("Camera", "CCDTemperature") in dp


def test_delete_group(global_mmcore: CMMCorePlus, qtbot: QtBot):
    gp = GroupPresetTableWidget()
    qtbot.addWidget(gp)
    mmc = global_mmcore

    assert "Camera" in mmc.getAvailableConfigGroups()

    for r in range(gp.table_wdg.rowCount()):
        group_name = gp.table_wdg.item(r, 0).text()

        if group_name == "Camera":
            with qtbot.waitSignal(mmc.events.configGroupDeleted):
                mmc.deleteConfigGroup("Camera")
            break

    assert "Camera" not in mmc.getAvailableConfigGroups()
    groups_in_table = [
        gp.table_wdg.item(r, 0).text() for r in range(gp.table_wdg.rowCount())
    ]

    assert "Camera" not in groups_in_table
    assert gp.table_wdg.rowCount() == 8


def test_add_preset(global_mmcore: CMMCorePlus, qtbot: QtBot):
    add_prs = AddPresetWidget("Channel")
    qtbot.addWidget(add_prs)
    gp = GroupPresetTableWidget()
    qtbot.addWidget(gp)
    mmc = global_mmcore

    add_prs.preset_name_lineedit.setText("New")

    dapi_values = []
    for k in mmc.getConfigData("Channel", "DAPI").dict().values():
        values = list(k.values())
        if len(values) > 1:
            dapi_values.extend(iter(values))
        else:
            dapi_values.append(values[0])

    for i in range(add_prs.table.rowCount()):
        add_prs.table.cellWidget(i, 1).setValue(dapi_values[i])

    with pytest.warns(UserWarning):
        add_prs.add_preset_button.click()
        assert add_prs.info_lbl.text() == "'DAPI' already has the same properties!"

    add_prs.table.cellWidget(3, 1).setValue("Noise")
    add_prs.add_preset_button.click()
    assert add_prs.info_lbl.text() == "'New' has been added!"

    assert "New" in mmc.getAvailableConfigs("Channel")

    dpv = [(k[0], k[1], k[2]) for k in mmc.getConfigData("Channel", "New")]
    assert dpv == [
        ("Dichroic", "Label", "400DCLP"),
        ("Emission", "Label", "Chroma-HQ620"),
        ("Excitation", "Label", "Chroma-D360"),
        ("Camera", "Mode", "Noise"),
        ("Multi Shutter", "Physical Shutter 1", "Undefined"),
        ("Multi Shutter", "Physical Shutter 2", "Shutter"),
        ("Multi Shutter", "Physical Shutter 3", "StateDev Shutter"),
        ("Multi Shutter", "Physical Shutter 4", "Undefined"),
        ("StateDev Shutter", "State Device", "StateDev"),
        ("StateDev", "Label", "State-1"),
    ]

    for r in range(gp.table_wdg.rowCount()):
        group_name = gp.table_wdg.item(r, 0).text()
        if group_name == "Channel":
            wdg = cast(PresetsWidget, gp.table_wdg.cellWidget(r, 1))
            assert wdg.allowedValues() == mmc.getAvailableConfigs("Channel")
            break


def test_edit_preset(global_mmcore: CMMCorePlus, qtbot: QtBot):
    edit_ps = EditPresetWidget("Objective", "10X")
    qtbot.addWidget(edit_ps)
    mmc = global_mmcore

    assert edit_ps.table.item(0, 0).text() == "Objective-State"
    wdg = edit_ps.table.cellWidget(0, 1)
    wdg.setValue(3)

    with pytest.warns(UserWarning):
        edit_ps.apply_button.click()
        assert edit_ps.info_lbl.text() == "'20X' already has the same properties!"

    wdg.setValue(5)
    edit_ps.apply_button.click()

    dpv = [(k[0], k[1], k[2]) for k in mmc.getConfigData("Objective", "10X")]
    assert dpv == [("Objective", "State", "5")]


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

    with qtbot.waitSignal(mmc.events.configDeleted):
        mmc.deleteConfig("Camera", "LowRes")

    assert "LowRes" not in mmc.getAvailableConfigs("Camera")
    wdg = cast(PresetsWidget, gp.table_wdg.cellWidget(camera_group_row, 1))
    assert "LowRes" not in wdg.allowedValues()


def test_save_cfg(global_mmcore: CMMCorePlus, qtbot: QtBot):
    with tempfile.TemporaryDirectory() as tmp:

        def _path(*args, **kwargs):
            return Path(tmp) / "test", None

        with patch.object(QFileDialog, "getSaveFileName", _path):
            gp = GroupPresetTableWidget()
            qtbot.addWidget(gp)

            gp._save_cfg()
            assert (Path(tmp) / "test.cfg").exists()
