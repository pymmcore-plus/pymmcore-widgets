from __future__ import annotations

from typing import TYPE_CHECKING

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

    mmc.setProperty("Objective", "Label", "Nikon 10X S Fluor")
    assert mmc.getPixelSizeUm() == 1.0
    _image_size_mm_x, _image_size_mm_y = _get_image_size()
    assert _image_size_mm_x == 0.512
    assert _image_size_mm_y == 0.512

    # center
    assert hcs.FOV_selector.tab_wdg.currentIndex() == 0
    scene_width = hcs.FOV_selector.scene.sceneRect().width()
    scene_height = hcs.FOV_selector.scene.sceneRect().height()
    assert scene_width == 200
    assert scene_height == 200
    items = list(hcs.FOV_selector.scene.items())
    assert len(items) == 2
    fov = items[0]
    well = items[1]
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
    fov = items[0]
    well = items[1]
    assert isinstance(fov, FOVPoints)
    assert isinstance(well, QGraphicsEllipseItem)
    well_size_mm_x, well_size_mm_y = hcs.wp.get_well_size()
    assert fov._x_size == (160 * _image_size_mm_x) / well_size_mm_x
    assert fov._y_size == (160 * _image_size_mm_y) / well_size_mm_y

    hcs.wp_combo.setCurrentText("standard 384")
    assert len(hcs.scene.items()) == 384
    items = list(hcs.FOV_selector.scene.items())
    fov = items[0]
    well = items[1]
    assert isinstance(fov, FOVPoints)
    assert isinstance(well, QGraphicsRectItem)
    well_size_mm_x, well_size_mm_y = hcs.wp.get_well_size()
    assert fov._x_size == (160 * _image_size_mm_x) / well_size_mm_x
    assert fov._y_size == (160 * _image_size_mm_y) / well_size_mm_y

    # random
    hcs.tabwidget.setCurrentIndex(1)
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
    hcs.FOV_selector.rows.setValue(3)
    hcs.FOV_selector.cols.setValue(3)
    hcs.FOV_selector.spacing_x.setValue(500.0)
    hcs.FOV_selector.spacing_y.setValue(500.0)
    items = list(hcs.FOV_selector.scene.items())
    assert len(items) == 11
    fovs = items[:9]
    for fov in fovs:
        assert isinstance(fov, FOVPoints)
