from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_widgets import ConfigGroupsEditor

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_config_groups_editor(qtbot: QtBot) -> None:
    wdg = ConfigGroupsEditor()
    qtbot.addWidget(wdg)
    wdg.show()
    assert wdg.isVisible()
