from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import Mock, call

import pytest
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QGraphicsEllipseItem, QGraphicsRectItem, QTableWidgetItem
from useq import MDASequence

from pymmcore_widgets._hcs_widget._calibration_widget import PlateCalibration
from pymmcore_widgets._hcs_widget._graphics_items import FOVPoints, Well, WellArea
from pymmcore_widgets._hcs_widget._main_hcs_widget import HCSWidget
from pymmcore_widgets._util import PLATE_FROM_CALIBRATION

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


@pytest.fixture()
def hcs_wdg(global_mmcore, qtbot: QtBot):
    hcs = HCSWidget(include_run_button=True, mmcore=global_mmcore)
    hcs._set_enabled(True)
    mmc = hcs._mmc
    cal = hcs.calibration
    qtbot.add_widget(hcs)
    with qtbot.waitSignal(hcs.wp_combo.currentTextChanged):
        hcs.wp_combo.setCurrentText("standard 6")
    return hcs, mmc, cal


def _get_image_size(mmc: CMMCorePlus):
    _cam_x = mmc.getROI(mmc.getCameraDevice())[-2]
    _cam_y = mmc.getROI(mmc.getCameraDevice())[-1]
    assert _cam_x == 512
    assert _cam_y == 512
    _image_size_mm_x = (_cam_x * mmc.getPixelSizeUm()) / 1000
    _image_size_mm_y = (_cam_y * mmc.getPixelSizeUm()) / 1000
    return _image_size_mm_x, _image_size_mm_y


def test_hcs_plate_selection(hcs_wdg: tuple[HCSWidget, Any, Any], qtbot: QtBot):
    hcs, _, _ = hcs_wdg

    assert hcs.tabwidget.currentIndex() == 0
    assert hcs.tabwidget.tabText(0) == "  Plate and FOVs Selection  "

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

    with qtbot.waitSignal(hcs.plate.plate_updated):
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


def test_hcs_fov_selection_FOVPoints_size(
    hcs_wdg: tuple[HCSWidget, CMMCorePlus, Any], qtbot: QtBot
):
    hcs, mmc, _ = hcs_wdg

    assert hcs.tabwidget.currentIndex() == 0
    assert hcs.tabwidget.tabText(0) == "  Plate and FOVs Selection  "
    assert hcs.FOV_selector.tab_wdg.currentIndex() == 0
    assert hcs.FOV_selector.tab_wdg.tabText(0) == "Center"

    assert hcs.wp_combo.currentText() == "standard 6"
    assert len(hcs.scene.items()) == 6

    scene_width = hcs.FOV_selector.scene.sceneRect().width()
    scene_height = hcs.FOV_selector.scene.sceneRect().height()
    assert scene_width == 200
    assert scene_height == 200

    assert mmc.getPixelSizeUm() == 1.0
    _image_size_mm_x, _image_size_mm_y = _get_image_size(mmc)
    assert _image_size_mm_x == 0.512
    assert _image_size_mm_y == 0.512
    fov, well = list(hcs.FOV_selector.scene.items())
    assert isinstance(fov, FOVPoints)
    assert isinstance(well, QGraphicsEllipseItem)
    assert fov._getPositionsInfo() == (scene_width / 2, scene_height / 2, 160, 160)
    assert fov._x_size == (160 * _image_size_mm_x) / hcs.wp.well_size_x
    assert fov._y_size == (160 * _image_size_mm_y) / hcs.wp.well_size_y
    assert fov._x_size == fov._y_size == 2.3540229885057475

    mmc.setProperty("Objective", "Label", "Nikon 20X Plan Fluor ELWD")
    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        mmc.events.pixelSizeChanged.emit(mmc.getPixelSizeUm())
    assert mmc.getPixelSizeUm() == 0.5
    _image_size_mm_x, _image_size_mm_y = _get_image_size(mmc)
    assert _image_size_mm_x == 0.256
    assert _image_size_mm_y == 0.256
    items = list(hcs.FOV_selector.scene.items())
    assert len(items) == 2
    fov, well = items
    assert isinstance(fov, FOVPoints)
    assert isinstance(well, QGraphicsEllipseItem)
    assert fov._getPositionsInfo() == (scene_width / 2, scene_height / 2, 160, 160)
    assert fov._x_size == (160 * _image_size_mm_x) / hcs.wp.well_size_x
    assert fov._y_size == (160 * _image_size_mm_y) / hcs.wp.well_size_y
    assert fov._x_size == fov._y_size == 1.1770114942528738


def test_hcs_fov_selection_center(
    hcs_wdg: tuple[HCSWidget, CMMCorePlus, Any], qtbot: QtBot
):
    hcs, _, _ = hcs_wdg

    assert hcs.tabwidget.currentIndex() == 0
    assert hcs.tabwidget.tabText(0) == "  Plate and FOVs Selection  "
    assert hcs.FOV_selector.tab_wdg.currentIndex() == 0
    assert hcs.FOV_selector.tab_wdg.tabText(0) == "Center"

    assert hcs.wp_combo.currentText() == "standard 6"
    assert len(hcs.scene.items()) == 6

    with qtbot.waitSignal(hcs.wp_combo.currentTextChanged):
        hcs.wp_combo.setCurrentText("standard 384")
    assert len(hcs.scene.items()) == 384
    items = list(hcs.FOV_selector.scene.items())
    assert len(items) == 2
    fov, well = items
    assert isinstance(fov, FOVPoints)
    assert isinstance(well, QGraphicsRectItem)


def test_hcs_fov_selection_random(hcs_wdg: tuple[HCSWidget, Any, Any], qtbot: QtBot):
    hcs, _, _ = hcs_wdg

    assert hcs.tabwidget.currentIndex() == 0
    assert hcs.tabwidget.tabText(0) == "  Plate and FOVs Selection  "
    hcs.tabwidget.setCurrentIndex(1)
    assert hcs.FOV_selector.tab_wdg.tabText(1) == "Random"

    assert hcs.wp_combo.currentText() == "standard 6"
    assert len(hcs.scene.items()) == 6

    hcs.FOV_selector.number_of_FOV.setValue(3)
    assert len(hcs.FOV_selector.scene.items()) == 5
    items = list(hcs.FOV_selector.scene.items())
    well = items[-1]
    well_area = items[-2]
    fovs = items[:3]
    assert isinstance(well, QGraphicsEllipseItem)
    assert isinstance(well_area, WellArea)
    for i in fovs:
        assert isinstance(i, FOVPoints)

    w, h = hcs.wp.well_size_x, hcs.wp.well_size_y
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


def test_hcs_fov_selection_grid(
    hcs_wdg: tuple[HCSWidget, CMMCorePlus, Any], qtbot: QtBot
):
    hcs, mmc, _ = hcs_wdg

    assert hcs.tabwidget.currentIndex() == 0
    assert hcs.tabwidget.tabText(0) == "  Plate and FOVs Selection  "
    hcs.tabwidget.setCurrentIndex(2)
    assert hcs.FOV_selector.tab_wdg.tabText(2) == "Grid"

    with qtbot.waitSignal(hcs.wp_combo.currentTextChanged):
        hcs.wp_combo.setCurrentText("standard 384")
    assert len(hcs.scene.items()) == 384

    hcs.FOV_selector.rows.setValue(3)
    hcs.FOV_selector.cols.setValue(3)
    hcs.FOV_selector.spacing_x.setValue(500.0)
    hcs.FOV_selector.spacing_y.setValue(500.0)
    items = list(hcs.FOV_selector.scene.items())
    assert len(items) == 10
    well = items[-1]
    assert isinstance(well, QGraphicsRectItem)

    _image_size_mm_x, _image_size_mm_y = _get_image_size(mmc)
    fovs = items[:9]
    for fov in fovs:
        assert isinstance(fov, FOVPoints)
        assert fov._x_size == (160 * _image_size_mm_x) / hcs.wp.well_size_x
        assert fov._y_size == (160 * _image_size_mm_y) / hcs.wp.well_size_y

    fov_1 = cast(FOVPoints, items[4])
    fov_2 = cast(FOVPoints, items[5])
    cx, cy, w, h = fov_1._getPositionsInfo()
    assert (round(cx, 2), round(cy, 2), w, h) == (100.00, 100.00, 160, 160)
    cx, cy, w, h = fov_2._getPositionsInfo()
    assert (round(cx, 2), round(cy, 2), w, h) == (140.48, 100.00, 160, 160)


def test_calibration_label(
    hcs_wdg: tuple[HCSWidget, Any, PlateCalibration], qtbot: QtBot
):
    hcs, _, cal = hcs_wdg

    hcs.wp_combo.setCurrentText("standard 96")
    assert hcs.wp_combo.currentText() == "standard 96"
    assert len(hcs.scene.items()) == 96
    assert not [item for item in hcs.scene.items() if item.isSelected()]

    hcs.tabwidget.setCurrentIndex(1)
    assert hcs.tabwidget.tabText(1) == "  Plate Calibration  "

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


def test_calibration_one_well(
    hcs_wdg: tuple[HCSWidget, CMMCorePlus, PlateCalibration], qtbot: QtBot
):
    hcs, mmc, cal = hcs_wdg

    hcs.tabwidget.setCurrentIndex(1)
    assert hcs.tabwidget.tabText(1) == "  Plate Calibration  "

    assert cal.cal_lbl.text() == "Plate non Calibrated!"

    assert hcs.wp_combo.currentText() == "standard 6"
    assert len(hcs.scene.items()) == 6
    assert not [item for item in hcs.scene.items() if item.isSelected()]

    assert cal._calibration_combo.currentText() == "1 Well (A1)"

    assert not cal.table_1.isHidden()
    assert cal.table_2.isHidden()

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
    with pytest.warns(match=error):
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
    with pytest.warns(match=error):
        cal._calibrate_plate()

    cal.table_1.tb.removeRow(3)

    assert cal._get_well_center(cal.table_1) == (0.0, 0.0)

    cal._calibrate_plate()
    assert cal.cal_lbl.text() == "Plate Calibrated!"

    assert cal.plate_angle_deg == 0.0
    assert not cal.plate_rotation_matrix


def test_calibration_one_well_square(
    hcs_wdg: tuple[HCSWidget, Any, PlateCalibration], qtbot: QtBot
):
    hcs, _, cal = hcs_wdg

    hcs.tabwidget.setCurrentIndex(1)
    assert hcs.tabwidget.tabText(1) == "  Plate Calibration  "

    assert cal.cal_lbl.text() == "Plate non Calibrated!"

    hcs.wp_combo.setCurrentText("standard 384")
    assert hcs.wp_combo.currentText() == "standard 384"
    assert len(hcs.scene.items()) == 384
    assert not [item for item in hcs.scene.items() if item.isSelected()]

    assert cal._calibration_combo.currentText() == "1 Well (A1)"

    assert not cal.table_1.isHidden()
    assert cal.table_2.isHidden()

    cal.table_1.tb.insertRow(0)
    cal.table_1.tb.setItem(0, 0, QTableWidgetItem("Well A1_pos000"))
    cal.table_1.tb.setItem(0, 1, QTableWidgetItem("-50.0"))
    cal.table_1.tb.setItem(0, 2, QTableWidgetItem("50.0"))
    assert cal.table_1.tb.rowCount() == 1

    error = "Not enough points for Well A1. Add 2 or 4 points to the table."
    with pytest.warns(match=error):
        cal._calibrate_plate()

    cal.table_1.tb.insertRow(1)
    cal.table_1.tb.setItem(1, 0, QTableWidgetItem("Well A1_pos001"))
    cal.table_1.tb.setItem(1, 1, QTableWidgetItem("50.0"))
    cal.table_1.tb.setItem(1, 2, QTableWidgetItem("-50.0"))

    assert cal.table_1.tb.rowCount() == 2

    assert cal._get_well_center(cal.table_1) == (0.0, 0.0)

    cal._calibrate_plate()
    assert cal.cal_lbl.text() == "Plate Calibrated!"

    assert cal.plate_angle_deg == 0.0
    assert not cal.plate_rotation_matrix


def test_calibration_two_wells(
    hcs_wdg: tuple[HCSWidget, Any, PlateCalibration], qtbot: QtBot
):
    hcs, _, cal = hcs_wdg

    hcs.tabwidget.setCurrentIndex(1)
    assert hcs.tabwidget.tabText(1) == "  Plate Calibration  "

    assert cal.cal_lbl.text() == "Plate non Calibrated!"

    assert hcs.wp_combo.currentText() == "standard 6"
    assert len(hcs.scene.items()) == 6
    assert not [item for item in hcs.scene.items() if item.isSelected()]

    cal._calibration_combo.setCurrentText("2 Wells (A1,  A3)")

    assert not cal.table_1.isHidden()
    assert not cal.table_2.isHidden()

    cal.table_1.tb.setRowCount(3)
    cal.table_2.tb.setRowCount(3)
    # A1
    cal.table_1.tb.setItem(0, 0, QTableWidgetItem("Well A1_pos000"))
    cal.table_1.tb.setItem(0, 1, QTableWidgetItem("-50"))
    cal.table_1.tb.setItem(0, 2, QTableWidgetItem("0"))
    cal.table_1.tb.setItem(1, 0, QTableWidgetItem("Well A1_pos001"))
    cal.table_1.tb.setItem(1, 1, QTableWidgetItem("0"))
    cal.table_1.tb.setItem(1, 2, QTableWidgetItem("50"))
    cal.table_1.tb.setItem(2, 0, QTableWidgetItem("Well A1_pos002"))
    cal.table_1.tb.setItem(2, 1, QTableWidgetItem("50"))
    cal.table_1.tb.setItem(2, 2, QTableWidgetItem("0"))
    # A3
    cal.table_2.tb.setItem(0, 0, QTableWidgetItem("Well A3_pos000"))
    cal.table_2.tb.setItem(0, 1, QTableWidgetItem("1364.213562373095"))
    cal.table_2.tb.setItem(0, 2, QTableWidgetItem("1414.2135623730949"))
    cal.table_2.tb.setItem(1, 0, QTableWidgetItem("Well A3_pos001"))
    cal.table_2.tb.setItem(1, 1, QTableWidgetItem("1414.213562373095"))
    cal.table_2.tb.setItem(1, 2, QTableWidgetItem("1364.2135623730949"))
    cal.table_2.tb.setItem(2, 0, QTableWidgetItem("Well A3_pos002"))
    cal.table_2.tb.setItem(2, 1, QTableWidgetItem("1464.213562373095"))
    cal.table_2.tb.setItem(2, 2, QTableWidgetItem("1414.2135623730949"))

    assert cal.table_1.tb.rowCount() == 3
    assert cal.table_2.tb.rowCount() == 3

    assert cal._get_well_center(cal.table_1) == (0.0, 0.0)
    assert cal._get_well_center(cal.table_2) == (1414.2135623730956, 1414.2135623730924)

    cal._calibrate_plate()

    assert round(cal.plate_angle_deg) == -45.0
    assert (
        str(cal.plate_rotation_matrix)
        == "[[ 0.70710678  0.70710678]\n [-0.70710678  0.70710678]]"
    )
    assert cal.cal_lbl.text() == "Plate Calibrated!"


def test_calibration_from_calibration(
    hcs_wdg: tuple[HCSWidget, Any, PlateCalibration], qtbot: QtBot
):
    hcs, _, cal = hcs_wdg

    hcs.tabwidget.setCurrentIndex(1)
    assert hcs.tabwidget.tabText(1) == "  Plate Calibration  "

    assert cal.cal_lbl.text() == "Plate non Calibrated!"

    hcs.wp_combo.setCurrentText(PLATE_FROM_CALIBRATION)
    assert hcs.wp_combo.currentText() == PLATE_FROM_CALIBRATION
    assert len(hcs.scene.items()) == 1
    assert len([item for item in hcs.scene.items() if item.isSelected()]) == 1

    assert cal._calibration_combo.currentText() == "1 Well (A1)"
    assert (
        len(
            [
                cal._calibration_combo.itemText(i)
                for i in range(cal._calibration_combo.count())
            ]
        )
        == 1
    )

    assert not cal.table_1.isHidden()
    assert cal.table_2.isHidden()

    cal.table_1.tb.setRowCount(2)
    cal.table_1.tb.setItem(0, 0, QTableWidgetItem("Well A1_pos000"))
    cal.table_1.tb.setItem(0, 1, QTableWidgetItem("-50.0"))
    cal.table_1.tb.setItem(0, 2, QTableWidgetItem("50.0"))
    cal.table_1.tb.setItem(1, 0, QTableWidgetItem("Well A1_pos001"))
    cal.table_1.tb.setItem(1, 1, QTableWidgetItem("50.0"))
    cal.table_1.tb.setItem(1, 2, QTableWidgetItem("-50.0"))
    assert cal.table_1.tb.rowCount() == 2

    assert cal._get_well_center(cal.table_1) == (0.0, 0.0)

    mock = Mock()
    cal.PlateFromCalibration.connect(mock)

    with qtbot.waitSignal(cal.PlateFromCalibration):
        cal._calibrate_plate()

    pos = cal._get_pos_from_table(cal.table_1)
    mock.assert_has_calls([call(pos)])

    assert cal.cal_lbl.text() == "Plate Calibrated!"

    assert cal.plate_angle_deg == 0.0
    assert not cal.plate_rotation_matrix


def test_generate_pos_list(
    hcs_wdg: tuple[HCSWidget, Any, PlateCalibration], qtbot: QtBot
):
    hcs, _, cal = hcs_wdg
    pos_table = hcs.ch_and_pos_list.stage_tableWidget

    hcs.wp_combo.setCurrentText("standard 384")
    assert hcs.wp_combo.currentText() == "standard 384"
    assert len(hcs.scene.items()) == 384

    wells = []
    for item in reversed(hcs.scene.items()):
        assert isinstance(item, Well)
        well, row, col = item._getPos()
        if col in {0, 1} and row in {0, 1}:
            item.setSelected(True)
            wells.append(well)
    assert len([item for item in hcs.scene.items() if item.isSelected()]) == 4
    assert wells == ["A1", "A2", "B1", "B2"]

    assert cal._calibration_combo.currentText() == "1 Well (A1)"

    cal.table_1.tb.setRowCount(2)
    cal.table_1.tb.setItem(0, 0, QTableWidgetItem("Well A1_pos000"))
    cal.table_1.tb.setItem(0, 1, QTableWidgetItem("-50.0"))
    cal.table_1.tb.setItem(0, 2, QTableWidgetItem("50.0"))
    cal.table_1.tb.setItem(1, 0, QTableWidgetItem("Well A1_pos001"))
    cal.table_1.tb.setItem(1, 1, QTableWidgetItem("50.0"))
    cal.table_1.tb.setItem(1, 2, QTableWidgetItem("-50.0"))

    cal._calibrate_plate()
    assert cal.cal_lbl.text() == "Plate Calibrated!"

    assert hcs.ch_and_pos_list.z_combo.currentText() == "Z"
    assert not pos_table.rowCount()

    # center
    assert hcs.FOV_selector.tab_wdg.currentIndex() == 0
    assert hcs.FOV_selector.tab_wdg.tabText(0) == "Center"

    hcs._generate_pos_list()
    assert pos_table.rowCount() == 4

    table_info = []
    for r in range(pos_table.rowCount()):
        well_name = pos_table.item(r, 0).text()
        _x = pos_table.item(r, 1).text()
        _y = pos_table.item(r, 2).text()
        _z = pos_table.item(r, 3).text()
        table_info.append((well_name, _x, _y, _z))

    assert table_info == [
        ("A1_pos000", "0.0", "0.0", "0.0"),
        ("A2_pos000", "4500.0", "0.0", "0.0"),
        ("B2_pos000", "4500.0", "-4500.0", "0.0"),
        ("B1_pos000", "0.0", "-4500.0", "0.0"),
    ]

    # random
    hcs.tabwidget.setCurrentIndex(1)
    assert hcs.FOV_selector.tab_wdg.tabText(1) == "Random"
    hcs.FOV_selector.number_of_FOV.setValue(2)

    hcs._generate_pos_list()
    assert pos_table.rowCount() == 8

    table_info = []
    for r in range(pos_table.rowCount()):
        well_name = pos_table.item(r, 0).text()
        table_info.append(well_name)

    assert table_info == [
        "A1_pos000",
        "A1_pos001",
        "A2_pos000",
        "A2_pos001",
        "B2_pos000",
        "B2_pos001",
        "B1_pos000",
        "B1_pos001",
    ]

    # grid
    hcs.tabwidget.setCurrentIndex(2)
    assert hcs.FOV_selector.tab_wdg.tabText(2) == "Grid"
    hcs.FOV_selector.rows.setValue(2)
    hcs.FOV_selector.cols.setValue(2)

    hcs._generate_pos_list()
    assert pos_table.rowCount() == 16

    table_info = []
    for r in range(pos_table.rowCount()):
        well_name = pos_table.item(r, 0).text()
        table_info.append(well_name)

    assert table_info == [
        "A1_pos000",
        "A1_pos001",
        "A1_pos002",
        "A1_pos003",
        "A2_pos000",
        "A2_pos001",
        "A2_pos002",
        "A2_pos003",
        "B2_pos000",
        "B2_pos001",
        "B2_pos002",
        "B2_pos003",
        "B1_pos000",
        "B1_pos001",
        "B1_pos002",
        "B1_pos003",
    ]


def test_hcs_state(hcs_wdg: tuple[HCSWidget, Any, PlateCalibration], qtbot: QtBot):
    hcs, _, cal = hcs_wdg
    mda = hcs.ch_and_pos_list
    pos_table = mda.stage_tableWidget

    hcs.wp_combo.setCurrentText("standard 384")
    assert hcs.wp_combo.currentText() == "standard 384"
    assert len(hcs.scene.items()) == 384

    for item in reversed(hcs.scene.items()):
        assert isinstance(item, Well)
        _, row, col = item._getPos()
        if col in {0, 1} and row in {0}:
            item.setSelected(True)
    assert len([item for item in hcs.scene.items() if item.isSelected()]) == 2

    assert cal._calibration_combo.currentText() == "1 Well (A1)"

    cal.table_1.tb.setRowCount(2)
    cal.table_1.tb.setItem(0, 0, QTableWidgetItem("Well A1_pos000"))
    cal.table_1.tb.setItem(0, 1, QTableWidgetItem("-50.0"))
    cal.table_1.tb.setItem(0, 2, QTableWidgetItem("50.0"))
    cal.table_1.tb.setItem(1, 0, QTableWidgetItem("Well A1_pos001"))
    cal.table_1.tb.setItem(1, 1, QTableWidgetItem("50.0"))
    cal.table_1.tb.setItem(1, 2, QTableWidgetItem("-50.0"))

    cal._calibrate_plate()
    assert cal.cal_lbl.text() == "Plate Calibrated!"

    assert mda.z_combo.currentText() == "Z"
    assert not pos_table.rowCount()

    assert hcs.FOV_selector.tab_wdg.currentIndex() == 0
    assert hcs.FOV_selector.tab_wdg.tabText(0) == "Center"

    # positions
    hcs._generate_pos_list()
    assert pos_table.rowCount() == 2

    # channels
    mda._add_channel()

    # time
    mda.time_groupBox.setChecked(True)
    mda.timepoints_spinBox.setValue(2)
    mda.interval_spinBox.setValue(1.00)
    mda.time_comboBox.setCurrentText("sec")

    # z stack
    mda.stack_group.setChecked(True)
    assert mda.z_tabWidget.currentIndex() == 0
    assert mda.z_tabWidget.tabText(0) == "RangeAround"
    mda.zrange_spinBox.setValue(2)
    mda.step_size_doubleSpinBox.setValue(1)

    state = hcs.get_state()

    sequence = MDASequence(
        channels=[
            {
                "config": "Cy5",
                "group": "Channel",
                "exposure": 100,
            }
        ],
        time_plan={"interval": {"seconds": 1.0}, "loops": 2},
        z_plan={"range": 2, "step": 1.0},
        axis_order="tpzc",
        stage_positions=(
            {"name": "A1_pos000", "x": 0.0, "y": 0.0, "z": 0.0},
            {"name": "A2_pos000", "x": 4500.0, "y": 0.0, "z": 0.0},
        ),
    )

    assert state.channels == sequence.channels
    assert state.time_plan == sequence.time_plan
    assert state.z_plan == sequence.z_plan
    assert state.axis_order == sequence.axis_order
    assert state.stage_positions == sequence.stage_positions


def test_save_positions(hcs_wdg: tuple[HCSWidget, Any, PlateCalibration], qtbot: QtBot):
    hcs, _, cal = hcs_wdg
    mda = hcs.ch_and_pos_list
    cal.A1_stage_coords_center = (0.0, 0.0)

    pos = [
        ("A1_pos000", "-100", "100", "0.0"),
        ("A1_pos001", "200", "200", "0.0"),
        ("A1_pos002", "300", "-300", "0.0"),
    ]

    mda.stage_tableWidget.setRowCount(3)
    for row, (pos_name, x, y, z) in enumerate(pos):
        name = QTableWidgetItem(pos_name)
        mda.stage_tableWidget.setItem(row, 0, name)
        stage_x = QTableWidgetItem(x)
        mda.stage_tableWidget.setItem(row, 1, stage_x)
        stage_y = QTableWidgetItem(y)
        mda.stage_tableWidget.setItem(row, 2, stage_y)
        stage_z = QTableWidgetItem(z)
        mda.stage_tableWidget.setItem(row, 3, stage_z)

    assert mda.stage_tableWidget.rowCount() == 3
    assert hcs._get_positions(3) == {
        "A1_center_coords": {"x": 0.0, "y": 0.0},
        "A1_pos000": {"x": -100.0, "y": 100.0, "z": 0.0},
        "A1_pos001": {"x": 200.0, "y": 200.0, "z": 0.0},
        "A1_pos002": {"x": 300.0, "y": -300.0, "z": 0.0},
    }


def test_load_positions(
    hcs_wdg: tuple[HCSWidget, Any, PlateCalibration], qtbot: QtBot, tmp_path: Path
):
    hcs, _, cal = hcs_wdg
    mda = hcs.ch_and_pos_list
    cal.A1_stage_coords_center = (100.0, 100.0)

    positions = {
        "A1_center_coords": {"x": 0.0, "y": 0.0},
        "A1_pos000": {"x": -100.0, "y": 100.0, "z": 0.0},
        "A1_pos001": {"x": 200.0, "y": 200.0, "z": 0.0},
        "A1_pos002": {"x": 300.0, "y": -300.0, "z": 0.0},
    }

    saved = tmp_path / "test.json"
    saved.write_text(json.dumps(positions))
    assert saved.exists()

    pos_list = json.loads(saved.read_text())

    hcs._add_loaded_positions_and_translate(pos_list)
    assert mda.stage_tableWidget.rowCount() == 3

    pos = [
        (
            mda.stage_tableWidget.item(r, 0).text(),
            mda.stage_tableWidget.item(r, 1).text(),
            mda.stage_tableWidget.item(r, 2).text(),
            mda.stage_tableWidget.item(r, 3).text(),
        )
        for r in range(3)
    ]

    assert pos == [
        ("A1_pos000", "0.0", "200.0", "0.0"),
        ("A1_pos001", "300.0", "300.0", "0.0"),
        ("A1_pos002", "400.0", "-200.0", "0.0"),
    ]
