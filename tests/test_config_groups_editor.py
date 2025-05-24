from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus.model import ConfigGroup

from pymmcore_widgets import ConfigGroupsEditor

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_config_groups_editor(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    original_groups = ConfigGroup.all_config_groups(global_mmcore)
    wdg = ConfigGroupsEditor.create_from_core(global_mmcore)
    qtbot.addWidget(wdg)
    wdg.show()

    # doing nothing should have returned the same data, unmodified.
    for new_group in wdg.data():
        original_group = original_groups[new_group.name]
        assert new_group == original_group
