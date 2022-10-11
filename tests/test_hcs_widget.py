from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt

from pymmcore_widgets._hcs_widget._graphics_items import Well
from pymmcore_widgets._hcs_widget._main_hcs_widget import HCSWidget
from pymmcore_widgets._hcs_widget._update_yaml_widget import UpdateYaml

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_hcs_plate_selection(qtbot: QtBot):
    hcs = HCSWidget()
    update_yaml = UpdateYaml()
    qtbot.add_widget(hcs)
    qtbot.add_widget(update_yaml)

    assert hcs.wp_combo.currentText() == "VWR 24  Plastic"
    assert len(hcs.scene.items()) == 24
    assert not [item for item in hcs.scene.items() if item.isSelected()]

    hcs.wp_combo.setCurrentText("standard 6")
    assert hcs.wp_combo.currentText() == "standard 6"
    assert len(hcs.scene.items()) == 6

    wells = []
    for item in reversed(hcs.scene.items()):
        assert isinstance(item, Well)
        well, _, col = item._getPos()
        wells.append(well)
        if col in {0, 1}:
            item.setSelected(True)
    assert wells == ["A1", "A2", "A3", "B1", "B2", "B3"]
    assert len([item for item in hcs.scene.items() if item.isSelected()]) == 4

    hcs.clear_button.click()
    assert not [item for item in hcs.scene.items() if item.isSelected()]

    hcs.custom_plate.click()
    assert hcs.plate._id.text() == ""
    assert hcs.plate._rows.value() == 0
    assert hcs.plate._cols.value() == 0
    assert hcs.plate._well_spacing_x.value() == 0
    assert hcs.plate._well_spacing_y.value() == 0
    assert hcs.plate._well_size_x.value() == 0
    assert hcs.plate._well_size_y.value() == 0
    assert not hcs.plate._circular_checkbox.isChecked()

    hcs.plate._id.setText("new_plate")
    hcs.plate._rows.setValue(3)
    hcs.plate._cols.setValue(3)
    hcs.plate._well_spacing_x.setValue(5)
    hcs.plate._well_spacing_y.setValue(5)
    hcs.plate._well_size_x.setValue(2)
    hcs.plate._well_size_y.setValue(2)
    hcs.plate._circular_checkbox.setChecked(True)

    with qtbot.waitSignal(hcs.plate.yamlUpdated):
        hcs.plate._ok_btn.click()

    items = [hcs.wp_combo.itemText(i) for i in range(hcs.wp_combo.count())]
    assert "new_plate" in items
    assert hcs.wp_combo.currentText() == "new_plate"
    assert len(hcs.scene.items()) == 9
    assert not [item for item in hcs.scene.items() if item.isSelected()]

    match = hcs.plate.plate_table.findItems("new_plate", Qt.MatchExactly)
    assert hcs.plate.plate_table.item(match[0].row(), 0).isSelected()

    hcs.plate._delete_btn.click()
    items = [hcs.wp_combo.itemText(i) for i in range(hcs.wp_combo.count())]
    assert "new_plate" not in items
