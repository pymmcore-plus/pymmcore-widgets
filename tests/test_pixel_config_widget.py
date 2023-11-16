from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt

from pymmcore_widgets._pixel_configuration_widget import (
    ID,
    NEW,
    ConfigMap,
    PixelConfigurationWidget,
)

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot

TEST_VALUE = [
    ConfigMap(
        "test_1", 0.5, [("Camera", "Binning", "1"), ("Camera", "BitDepth", "16")]
    ),
    ConfigMap(
        "test_2", 2.0, [("Camera", "Binning", "2"), ("Camera", "BitDepth", "12")]
    ),
]


def test_pixel_config_wdg(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)

    assert wdg.value() == [
        ConfigMap("Res10x", 1.0, [("Objective", "Label", "Nikon 10X S Fluor")]),
        ConfigMap("Res20x", 0.5, [("Objective", "Label", "Nikon 20X Plan Fluor ELWD")]),
        ConfigMap(
            "Res40x", 0.25, [("Objective", "Label", "Nikon 40X Plan Fluor ELWD")]
        ),
    ]

    assert wdg._props_selector._prop_table.getCheckedProperties() == [
        ("Objective", "Label", "Nikon 10X S Fluor")
    ]

    wdg.setValue(TEST_VALUE)
    assert wdg._props_selector._prop_table.getCheckedProperties() == [
        ("Camera", "Binning", "1"),
        ("Camera", "BitDepth", "16"),
    ]


def test_pixel_config_wdg_sys_cfg_load(qtbot: QtBot):
    # test that a new config is loaded correctly
    from pathlib import Path

    TEST_CONFIG = str(Path(__file__).parent / "test_config.cfg")
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)
    wdg._mmc.loadSystemConfiguration(TEST_CONFIG)
    assert wdg.value()


def test_pixel_config_wdg_define_configs(qtbot: QtBot, global_mmcore: CMMCorePlus):
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

    wdg.setValue(TEST_VALUE)

    wdg._px_table._table.item(0, 0).setText("new_test")
    wdg._px_table._table.cellWidget(0, 1).setValue(10)

    row_checkbox = wdg._props_selector._prop_table.item(0, 0)
    row_checkbox.setCheckState(Qt.CheckState.Checked)
    assert wdg._resID_map[0].properties == [
        ("Camera", "AllowMultiROI", "0"),
        ("Camera", "Binning", "1"),
        ("Camera", "BitDepth", "16"),
    ]

    wdg._on_apply()

    assert list(wdg._mmc.getAvailablePixelSizeConfigs()) == ["new_test", "test_2"]
    assert wdg._mmc.getPixelSizeUmByID("new_test") == 10
    assert wdg._mmc.getPixelSizeUmByID("test_2") == 2.0


def test_pixel_config_wdg_enabled(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)

    items = wdg._px_table._table.selectedItems()
    assert len(items) == 1
    assert wdg._props_selector.isEnabled()

    wdg._px_table._table.clearSelection()
    assert not wdg._props_selector.isEnabled()


def test_pixel_config_wdg_prop_selection(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)

    wdg._px_table._table.selectRow(1)
    assert wdg._props_selector.value() == [
        ("Objective", "Label", "Nikon 20X Plan Fluor ELWD")
    ]

    # set checked ("Camera", "AllowMultiROI", "0")
    row_checkbox = wdg._props_selector._prop_table.item(0, 0)

    row_checkbox.setCheckState(Qt.CheckState.Checked)
    # ("Camera", "AllowMultiROI", "0") should be in all configs
    assert any(
        ("Camera", "AllowMultiROI", "0") in wdg._resID_map[i].properties
        for i in wdg._resID_map
    )

    row_checkbox.setCheckState(Qt.CheckState.Unchecked)
    # ("Camera", "AllowMultiROI", "0") should be removed in all configs
    assert all(
        ("Camera", "AllowMultiROI", "0") not in wdg._resID_map[i].properties
        for i in wdg._resID_map
    )

    wdg._px_table._add_row()
    assert wdg._px_table.value()[-1][ID] == NEW
    wdg._resID_map[3].properties = [("Objective", "Label", "Nikon 20X Plan Fluor ELWD")]


def test_pixel_config_wdg_prop_change(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)

    # row 67 is the ("Objective", "Label") property
    row_wdg = wdg._props_selector._prop_table.cellWidget(67, 1)
    assert row_wdg.value() == "Nikon 10X S Fluor"

    row_wdg.setValue("Nikon 40X Plan Fluor ELWD")
    assert wdg._resID_map[0].properties == [
        ("Objective", "Label", "Nikon 40X Plan Fluor ELWD")
    ]


def test_pixel_config_wdg_errors(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)
