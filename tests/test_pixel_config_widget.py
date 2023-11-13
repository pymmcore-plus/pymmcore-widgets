from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt

from pymmcore_widgets._pixel_configuration_widget import (
    ID,
    NEW,
    PX,
    PixelConfigurationWidget,
)

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_pixel_config_wdg_load(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)

    assert wdg.value() == {
        "Res10x": {"px": 1.0, "props": [("Objective", "Label", "Nikon 10X S Fluor")]},
        "Res20x": {
            "px": 0.5,
            "props": [("Objective", "Label", "Nikon 20X Plan Fluor ELWD")],
        },
        "Res40x": {
            "px": 0.25,
            "props": [("Objective", "Label", "Nikon 40X Plan Fluor ELWD")],
        },
    }
    assert wdg._props_selector._prop_table.getCheckedProperties() == [
        ("Objective", "Label", "Nikon 10X S Fluor")
    ]


def test_pixel_config_wdg_prop_selection(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)

    wdg._px_table._table.selectRow(1)
    assert wdg._props_selector._prop_table.getCheckedProperties() == [
        ("Objective", "Label", "Nikon 20X Plan Fluor ELWD")
    ]

    # set checked ("Camera", "AllowMultiROI", "0")
    row_checkbox = wdg._props_selector._prop_table.item(0, 0)

    row_checkbox.setCheckState(Qt.CheckState.Checked)
    # ("Camera", "AllowMultiROI", "0") should be in all configs
    for x in [wdg._config_map[i].props for i in wdg._config_map]:
        assert ("Camera", "AllowMultiROI", "0") in x

    row_checkbox.setCheckState(Qt.CheckState.Unchecked)
    # ("Camera", "AllowMultiROI", "0") should be removed in all configs
    for x in [wdg._config_map[i].props for i in wdg._config_map]:
        assert ("Camera", "AllowMultiROI", "0") not in x

    wdg._px_table._add_row()
    assert wdg._px_table.value()[-1][ID] == NEW
    wdg._config_map[3].props = [("Objective", "Label", "Nikon 20X Plan Fluor ELWD")]


def test_pixel_config_wdg_prop_change(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)

    # row 67 is the ("Objective", "Label") property
    row_wdg = wdg._props_selector._prop_table.cellWidget(67, 1)
    assert row_wdg.value() == "Nikon 10X S Fluor"

    row_wdg.setValue("Nikon 40X Plan Fluor ELWD")
    assert wdg._config_map[0].props == [
        ("Objective", "Label", "Nikon 40X Plan Fluor ELWD")
    ]


def test_pixel_config_wdg_core(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)

    assert list(wdg._mmc.getAvailablePixelSizeConfigs()) == [
        "Res10x",
        "Res20x",
        "Res40x",
    ]

    wdg._px_table._remove_all()
    wdg._on_apply()

    # assert that all configs are removed
    assert not wdg._mmc.getAvailablePixelSizeConfigs()

    wdg._px_table._add_row()
    assert wdg._px_table.value()[-1][ID] == NEW
    assert wdg._px_table.value()[-1][PX] == 0.0

    wdg._px_table._table.item(0, 0).setText("test")
    wdg._px_table._table.cellWidget(0, 1).setValue(10)

    assert wdg._config_map[0].resolutionID == "test"
    assert wdg._config_map[0].px_size == 10.0
    assert not wdg._config_map[0].props

    row_checkbox = wdg._props_selector._prop_table.item(0, 0)
    row_checkbox.setCheckState(Qt.CheckState.Checked)
    assert wdg._config_map[0].props == [("Camera", "AllowMultiROI", "0")]


def test_pixel_config_wdg_enabled(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)

    items = wdg._px_table._table.selectedItems()
    assert len(items) == 1
    assert wdg._props_selector.isEnabled()

    wdg._px_table._table.clearSelection()
    assert not wdg._props_selector.isEnabled()


def test_pixel_config_wdg_errors(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)
