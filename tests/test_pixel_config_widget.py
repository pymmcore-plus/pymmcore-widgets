from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt

from pymmcore_widgets._pixel_configuration_widget import PixelConfigurationWidget

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
