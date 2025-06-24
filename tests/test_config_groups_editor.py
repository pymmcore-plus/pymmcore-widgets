from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pymmcore_plus.model import ConfigGroup
from qtpy.QtCore import Qt

from pymmcore_widgets import ConfigGroupsEditor

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


@pytest.mark.xfail
def test_config_groups_editor(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    original_groups = ConfigGroup.all_config_groups(global_mmcore)
    wdg = ConfigGroupsEditor.create_from_core(global_mmcore)
    qtbot.addWidget(wdg)
    wdg.show()

    # doing nothing should have returned the same data, unmodified.
    for new_group in wdg.data():
        original_group = original_groups[new_group.name]
        assert new_group == original_group


def test_config_groups_editor_light_path_interaction(
    qtbot: QtBot, global_mmcore: CMMCorePlus
) -> None:
    """Test light path checkbox behavior when switching between presets."""
    # Create and show a ConfigGroupsEditor
    wdg = ConfigGroupsEditor.create_from_core(global_mmcore)
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.setCurrentGroup("Channel")
    wdg.setCurrentPreset("Cy5")
    light_path_props = wdg._light_path_group.props

    # Find the first checked item in the light path properties
    row, item = next(
        (row, item)
        for row in range(light_path_props.rowCount())
        if (item := light_path_props.item(row, 0))
        and item.checkState() == Qt.CheckState.Checked
    )

    # Uncheck the row
    item.setCheckState(Qt.CheckState.Unchecked)
    assert item.checkState() == Qt.CheckState.Unchecked

    # Select the DAPI preset (2nd item in the presets list)
    wdg.setCurrentPreset("DAPI")

    # Assert that the row is checked again
    # (because DAPI preset should load its own settings)
    item = light_path_props.item(row, 0)
    assert item and item.checkState() == Qt.CheckState.Checked

    # Select the Cy5 preset again
    wdg.setCurrentPreset("Cy5")

    # Assert that the row returns to being unchecked as we had set it
    # Note: This tests that our manual modification was preserved and restored
    item = light_path_props.item(row, 0)
    assert item and item.checkState() == Qt.CheckState.Unchecked
