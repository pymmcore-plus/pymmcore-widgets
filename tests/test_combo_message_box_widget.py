from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_widgets._util import ComboMessageBox

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_combo_message_box_widget(qtbot: QtBot):
    items = ["item_1", "item_2", "item_3"]

    wdg = ComboMessageBox(items)
    qtbot.add_widget(wdg)

    assert wdg._combo.count() == 3

    wdg._combo.setCurrentIndex(1)
    assert wdg._combo.currentText() == "item_2"

    wdg._combo.setCurrentText("item_3")
    assert wdg._combo.currentText() == "item_3"
