from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QGraphicsEllipseItem, QGraphicsRectItem

from pymmcore_widgets._hcs_widget._graphics_items import FOVPoints, Well, WellArea
from pymmcore_widgets._hcs_widget._main_hcs_widget import HCSWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_hcs_plate_selection(qtbot: QtBot):
    hcs = HCSWidget()
    qtbot.add_widget(hcs)

    assert hcs.tabwidget.currentIndex() == 0
    assert hcs.tabwidget.tabText(0) == "  Plate and FOVs Selection  "

    hcs.wp_combo.setCurrentText("standard 6")
    assert hcs.wp_combo.currentText() == "standard 6"
    assert len(hcs.scene.items()) == 6
    assert not [item for item in hcs.scene.items() if item.isSelected()]

    wells = []
    for item in reversed(hcs.scene.items()):
        assert isinstance(item, Well)
        well, _, col = item._getPos()
        wells.append(well)
        if col in {0, 1}:
            item.setSelected(True)
    assert wells == ["A1", "A2", "A3", "B1", "B2", "B3"]
    assert len([item for item in hcs.scene.items() if item.isSelected()]) == 4

    well_order = hcs.scene._get_plate_positions()
    assert well_order == [("A1", 0, 0), ("A2", 0, 1), ("B2", 1, 1), ("B1", 1, 0)]

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

    hcs.plate.close()


def test_hcs_fov_selection(qtbot: QtBot, global_mmcore: CMMCorePlus):

    mmc = global_mmcore
    hcs = HCSWidget()
    qtbot.add_widget(hcs)

    def _get_image_size():
        _cam_x = mmc.getROI(mmc.getCameraDevice())[-2]
        _cam_y = mmc.getROI(mmc.getCameraDevice())[-1]
        assert _cam_x == 512
        assert _cam_y == 512
        _image_size_mm_x = (_cam_x * mmc.getPixelSizeUm()) / 1000
        _image_size_mm_y = (_cam_y * mmc.getPixelSizeUm()) / 1000
        return _image_size_mm_x, _image_size_mm_y

    assert hcs.tabwidget.currentIndex() == 0
    assert hcs.tabwidget.tabText(0) == "  Plate and FOVs Selection  "

    hcs.wp_combo.setCurrentText("standard 6")
    assert hcs.wp_combo.currentText() == "standard 6"
    assert len(hcs.scene.items()) == 6
    assert not [item for item in hcs.scene.items() if item.isSelected()]

    mmc.setProperty("Objective", "Label", "Nikon 10X S Fluor")
    assert mmc.getPixelSizeUm() == 1.0
    _image_size_mm_x, _image_size_mm_y = _get_image_size()
    assert _image_size_mm_x == 0.512
    assert _image_size_mm_y == 0.512

    # center
    assert hcs.FOV_selector.tab_wdg.currentIndex() == 0
    assert hcs.FOV_selector.tab_wdg.tabText(0) == "Center"
    scene_width = hcs.FOV_selector.scene.sceneRect().width()
    scene_height = hcs.FOV_selector.scene.sceneRect().height()
    assert scene_width == 200
    assert scene_height == 200
    items = list(hcs.FOV_selector.scene.items())
    assert len(items) == 2
    fov, well = items
    assert isinstance(fov, FOVPoints)
    assert isinstance(well, QGraphicsEllipseItem)
    assert fov._getPositionsInfo() == (scene_width / 2, scene_height / 2, 160, 160)
    well_size_mm_x, well_size_mm_y = hcs.wp.get_well_size()
    assert fov._x_size == (160 * _image_size_mm_x) / well_size_mm_x
    assert fov._y_size == (160 * _image_size_mm_y) / well_size_mm_y

    mmc.setProperty("Objective", "Label", "Nikon 20X Plan Fluor ELWD")
    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        mmc.events.pixelSizeChanged.emit(mmc.getPixelSizeUm())
    assert mmc.getPixelSizeUm() == 0.5
    _image_size_mm_x, _image_size_mm_y = _get_image_size()
    assert _image_size_mm_x == 0.256
    assert _image_size_mm_y == 0.256

    items = list(hcs.FOV_selector.scene.items())
    assert len(items) == 2
    fov, well = items
    assert isinstance(fov, FOVPoints)
    assert isinstance(well, QGraphicsEllipseItem)
    well_size_mm_x, well_size_mm_y = hcs.wp.get_well_size()
    assert fov._x_size == (160 * _image_size_mm_x) / well_size_mm_x
    assert fov._y_size == (160 * _image_size_mm_y) / well_size_mm_y

    print("________")
    hcs.wp_combo.setCurrentText("standard 384")
    assert hcs.wp_combo.currentText() == "standard 384"
    assert len(hcs.scene.items()) == 384
    items = list(hcs.FOV_selector.scene.items())
    assert len(items) == 2
    fov, well = items
    print("             ***", fov)
    print("             ***", well)
    assert isinstance(fov, FOVPoints)
    assert isinstance(well, QGraphicsRectItem)
    _image_size_mm_x, _image_size_mm_y = _get_image_size()
    well_size_mm_x, well_size_mm_y = hcs.wp.get_well_size()
    assert fov._x_size == (160 * _image_size_mm_x) / well_size_mm_x
    assert fov._y_size == (160 * _image_size_mm_y) / well_size_mm_y

    # random
    hcs.tabwidget.setCurrentIndex(1)
    assert hcs.FOV_selector.tab_wdg.tabText(1) == "Random"
    hcs.FOV_selector.number_of_FOV.setValue(3)
    assert len(hcs.FOV_selector.scene.items()) == 5
    items = list(hcs.FOV_selector.scene.items())
    well = items[-1]
    well_area = items[-2]
    fovs = items[:3]
    assert isinstance(well, QGraphicsRectItem)
    assert isinstance(well_area, WellArea)
    for i in fovs:
        assert isinstance(i, FOVPoints)

    w, h = hcs.wp.get_well_size()
    ax = hcs.FOV_selector.plate_area_x
    ay = hcs.FOV_selector.plate_area_y
    assert ax.value() == w
    assert ay.value() == h
    assert well_area._w == (160 * ax.value()) / w
    assert well_area._h == (160 * ay.value()) / h

    hcs.FOV_selector.number_of_FOV.setValue(1)
    ax.setValue(3.0)
    ay.setValue(3.0)
    items = list(hcs.FOV_selector.scene.items())
    well_area = items[-2]
    fov_1 = items[0]
    assert isinstance(well_area, WellArea)
    assert isinstance(fov_1, FOVPoints)
    assert ax.value() != w
    assert ay.value() != h
    assert well_area._w == (160 * ax.value()) / w
    assert well_area._h == (160 * ay.value()) / h

    hcs.FOV_selector.random_button.click()

    items = list(hcs.FOV_selector.scene.items())
    fov_2 = items[0]
    assert isinstance(fov_2, FOVPoints)

    assert fov_1._x != fov_2._x
    assert fov_1._y != fov_2._y

    # grid
    hcs.tabwidget.setCurrentIndex(2)
    assert hcs.FOV_selector.tab_wdg.tabText(2) == "Grid"
    hcs.FOV_selector.rows.setValue(3)
    hcs.FOV_selector.cols.setValue(3)
    hcs.FOV_selector.spacing_x.setValue(500.0)
    hcs.FOV_selector.spacing_y.setValue(500.0)
    items = list(hcs.FOV_selector.scene.items())
    assert len(items) == 11
    well_area = items[-2]
    assert isinstance(well_area, WellArea)
    well_size_mm_x, well_size_mm_y = hcs.wp.get_well_size()
    fovs = items[:9]
    for fov in fovs:
        assert isinstance(fov, FOVPoints)
        assert fov._x_size == (160 * _image_size_mm_x) / well_size_mm_x
        assert fov._y_size == (160 * _image_size_mm_y) / well_size_mm_y

    fov_1 = cast(FOVPoints, items[4])
    fov_2 = cast(FOVPoints, items[5])
    assert fov_1._getPositionsInfo() == (100.0, 100.0, 160, 160)
    assert fov_2._getPositionsInfo() == (130.24, 100.0, 160, 160)


def test_calibration(qtbot: QtBot, global_mmcore: CMMCorePlus):

    mmc = global_mmcore
    hcs = HCSWidget()
    qtbot.add_widget(hcs)

    hcs.wp_combo.setCurrentText("standard 96")
    assert hcs.wp_combo.currentText() == "standard 96"
    assert len(hcs.scene.items()) == 96
    assert not [item for item in hcs.scene.items() if item.isSelected()]

    hcs.tabwidget.setCurrentIndex(1)
    assert hcs.tabwidget.tabText(1) == "  Plate Calibration  "

    cal = hcs.calibration

    assert cal.cal_lbl.text() == "Plate non Calibrated!"

    assert cal._calibration_combo.currentIndex() == 0
    assert cal._calibration_combo.currentText() == "1 Well (A1)"
    text = (
        "Calibrate Wells: A1\n"
        "\n"
        "Add 3 points on the circonference of the round well "
        "and click on 'Calibrate Plate'."
    )
    assert cal.info_lbl.text() == text

    cal._calibration_combo.setCurrentIndex(1)
    assert cal._calibration_combo.currentText() == "2 Wells (A1,  A12)"
    text = (
        "Calibrate Wells: A1,  A12\n"
        "\n"
        "Add 3 points on the circonference of the round well "
        "and click on 'Calibrate Plate'."
    )
    assert cal.info_lbl.text() == text

    hcs.wp_combo.setCurrentText("standard 384")
    assert hcs.wp_combo.currentText() == "standard 384"
    assert len(hcs.scene.items()) == 384
    assert not [item for item in hcs.scene.items() if item.isSelected()]

    cal._calibration_combo.setCurrentIndex(1)
    assert cal._calibration_combo.currentText() == "2 Wells (A1,  A24)"

    text = (
        "Calibrate Wells: A1,  A24\n"
        "\n"
        "Add 2 points (opposite vertices) "
        "or 4 points (1 point per side) "
        "and click on 'Calibrate Plate'."
    )
    assert cal.info_lbl.text() == text

    hcs.wp_combo.setCurrentText("standard 6")
    assert hcs.wp_combo.currentText() == "standard 6"
    assert len(hcs.scene.items()) == 6
    assert not [item for item in hcs.scene.items() if item.isSelected()]

    assert cal._calibration_combo.currentText() == "1 Well (A1)"

    mmc.setXYPosition(-50.0, 0.0)
    mmc.waitForDevice(mmc.getXYStageDevice())
    cal.table_1._add_pos()
    assert cal.table_1.tb.item(0, 0).text() == "Well A1_pos000"
    assert cal.table_1.tb.item(0, 1).text() == "-49.995"
    assert cal.table_1.tb.item(0, 2).text() == "-0.0"

    mmc.setXYPosition(0.0, 50.0)
    mmc.waitForDevice(mmc.getXYStageDevice())
    cal.table_1._add_pos()
    assert cal.table_1.tb.item(1, 0).text() == "Well A1_pos001"
    assert cal.table_1.tb.item(1, 1).text() == "-0.0"
    assert cal.table_1.tb.item(1, 2).text() == "49.995"

    error = "Not enough points for Well A1. Add 3 points to the table."
    with pytest.raises(ValueError, match=error):
        cal._calibrate_plate()

    mmc.setXYPosition(50.0, 0.0)
    mmc.waitForDevice(mmc.getXYStageDevice())
    cal.table_1._add_pos()
    assert cal.table_1.tb.item(2, 0).text() == "Well A1_pos002"
    assert cal.table_1.tb.item(2, 1).text() == "49.995"
    assert cal.table_1.tb.item(2, 2).text() == "-0.0"

    cal.table_1._add_pos()
    assert cal.table_1.tb.rowCount() == 4
    error = "Add only 3 points to the table."
    with pytest.raises(ValueError, match=error):
        cal._calibrate_plate()

    cal.table_1.tb.removeRow(3)
    cal._calibrate_plate()
    assert cal.cal_lbl.text() == "Plate Calibrated!"

    # TODO:
    # get coords calibration
    # test calibration with 2 wells
    # test square plate
    # test _from_calibration
