from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from pymmcore_plus.model import PixelSizePreset, Setting
from qtpy.QtCore import Qt

from pymmcore_widgets.config_presets._pixel_configuration_widget import (
    ID,
    NEW,
    PixelConfigurationWidget,
)

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot

TEST_VALUE = [
    PixelSizePreset(
        "test_1",
        [Setting("Camera", "Binning", "1"), Setting("Camera", "BitDepth", "16")],
        0.5,
        (0.5, 0.0, 0.0, 0.0, 0.5, 0.0),
    ),
    PixelSizePreset(
        "test_2",
        [Setting("Camera", "Binning", "2"), Setting("Camera", "BitDepth", "12")],
        2.0,
        (2, 0.0, 0.0, 0.0, 2, 0.0),
    ),
]


def test_pixel_config_wdg(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)

    assert wdg.value() == [
        PixelSizePreset(
            "Res10x", [Setting("Objective", "Label", "Nikon 10X S Fluor")], 1.0
        ),
        PixelSizePreset(
            "Res20x", [Setting("Objective", "Label", "Nikon 20X Plan Fluor ELWD")], 0.5
        ),
        PixelSizePreset(
            "Res40x", [Setting("Objective", "Label", "Nikon 40X Plan Fluor ELWD")], 0.25
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

    assert wdg.value()[0].affine == (0.5, 0.0, 0.0, 0.0, 0.5, 0.0)
    assert wdg.value()[1].affine == (2, 0.0, 0.0, 0.0, 2, 0.0)


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

    row_checkbox = wdg._props_selector._prop_table.item(0, 0)
    row_checkbox.setCheckState(Qt.CheckState.Checked)
    assert wdg._resID_map[0].settings == [
        ("Camera", "AllowMultiROI", "0"),
        ("Camera", "Binning", "1"),
        ("Camera", "BitDepth", "16"),
    ]
    assert wdg._resID_map[0].affine == (0.5, 0.0, 0.0, 0.0, 0.5, 0.0)

    wdg._on_apply()

    assert list(wdg._mmc.getAvailablePixelSizeConfigs()) == ["test_1", "test_2"]
    assert wdg._mmc.getPixelSizeAffineByID("test_1") == (0.5, 0.0, 0.0, 0.0, 0.5, 0.0)
    assert wdg._mmc.getPixelSizeAffineByID("test_2") == (2, 0.0, 0.0, 0.0, 2, 0.0)


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
        ("Camera", "AllowMultiROI", "0") in wdg._resID_map[i].settings
        for i in wdg._resID_map
    )

    row_checkbox.setCheckState(Qt.CheckState.Unchecked)
    # ("Camera", "AllowMultiROI", "0") should be removed in all configs
    assert all(
        ("Camera", "AllowMultiROI", "0") not in wdg._resID_map[i].settings
        for i in wdg._resID_map
    )

    wdg._px_table._add_row()
    assert wdg._px_table.value()[-1][ID] == NEW
    wdg._resID_map[3].settings = [("Objective", "Label", "Nikon 20X Plan Fluor ELWD")]


def test_pixel_config_wdg_prop_change(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)

    assert wdg._px_table._table.selectedItems()[0].text() == "Res10x"

    viewer_wdg = wdg._props_selector._prop_viewer.cellWidget(0, 1)
    assert viewer_wdg.value() == "Nikon 10X S Fluor"
    assert wdg._props_selector.value() == [("Objective", "Label", "Nikon 10X S Fluor")]

    # row 67 is the ("Objective", "Label") property
    prop_wdg = wdg._props_selector._prop_table.cellWidget(67, 1)
    assert prop_wdg.value() == "Nikon 10X S Fluor"

    viewer_wdg.setValue("Nikon 40X Plan Fluor ELWD")
    assert wdg._props_selector.value() == [
        ("Objective", "Label", "Nikon 40X Plan Fluor ELWD")
    ]
    assert prop_wdg.value() == "Nikon 40X Plan Fluor ELWD"


def test_pixel_config_wdg_px_table(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)

    assert wdg._px_table._table.selectedItems()[0].text() == "Res10x"
    assert wdg._props_selector.value() == [("Objective", "Label", "Nikon 10X S Fluor")]

    wdg._px_table._table.selectRow(1)
    assert wdg._px_table._table.selectedItems()[0].text() == "Res20x"
    assert wdg._props_selector.value() == [
        ("Objective", "Label", "Nikon 20X Plan Fluor ELWD")
    ]

    assert wdg._resID_map[1].pixel_size_um == 0.5
    spin = wdg._px_table._table.cellWidget(1, 1)
    spin.setValue(10)
    # the above setValue does not trigger the signal, so we need to manually call it
    spin.valueChanged.emit(10)
    assert wdg.value()[1].pixel_size_um == 10
    assert wdg._affine_table.value() == (10, 0.0, 0.0, 0.0, 10, 0.0)
    assert wdg._resID_map[1].pixel_size_um == 10
    assert wdg._resID_map[1].affine == (10, 0.0, 0.0, 0.0, 10, 0.0)


def test_pixel_config_wdg_errors(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)

    def _show_msg(msg: str):
        return msg

    wdg.setValue([PixelSizePreset("", [Setting("Camera", "AllowMultiROI", "0")], 0.5)])
    with patch.object(wdg, "_show_error_message", _show_msg):
        assert wdg._check_for_errors() == "All resolutionIDs must have a name."

    wdg.setValue(
        [
            PixelSizePreset("test", [Setting("Camera", "AllowMultiROI", "0")], 0.5),
            PixelSizePreset("test", [Setting("Camera", "AllowMultiROI", "1")], 1),
        ]
    )
    with patch.object(wdg, "_show_error_message", _show_msg):
        assert wdg._check_for_errors() == "There are duplicated resolutionIDs: ['test']"

    wdg.setValue([PixelSizePreset("test2", [], 1)])

    with patch.object(wdg, "_show_error_message", _show_msg):
        assert wdg._check_for_errors() == (
            "Each resolutionID must have at least one property."
        )


def test_pixel_config_wdg_warning(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)

    with pytest.warns(UserWarning, match="ResolutionID 'Res40x' already exists."):
        wdg._px_table._table.item(0, 0).setText("Res40x")


def p_delete_resID(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PixelConfigurationWidget()
    qtbot.addWidget(wdg)

    assert len(wdg._resID_map) == 3

    wdg._px_table._table.selectRow(1)
    assert wdg._px_table._table.selectedItems()[0].text() == "Res20x"

    wdg._px_table._remove_selected()

    assert len(wdg._resID_map) == 2
    assert wdg._resID_map[0].name == "Res10x"
    assert wdg._resID_map[1].name == "Res40x"
    assert wdg.value() == [
        PixelSizePreset(
            "Res10x", [Setting("Objective", "Label", "Nikon 10X S Fluor")], 1.0
        ),
        PixelSizePreset(
            "Res40x", [Setting("Objective", "Label", "Nikon 40X Plan Fluor ELWD")], 0.25
        ),
    ]
