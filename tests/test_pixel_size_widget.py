from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QTableWidgetItem

from pymmcore_widgets._pixel_size_widget import PixelSizeWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


OBJECTIVE_LABEL = 0
RESOLUTION_ID = 1
CAMERA_PX_SIZE = 2
MAGNIFICATION = 3
IMAGE_PX_SIZE = 4
LABEL_STATUS = 5


def test_pixel_size_widget(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore

    px_size_wdg = PixelSizeWidget("", mmcore=mmc)
    table = px_size_wdg.table
    obj = px_size_wdg._objective_device
    qtbot.addWidget(px_size_wdg)

    assert ["Res10x", "Res20x", "Res40x"] == list(mmc.getAvailablePixelSizeConfigs())
    assert px_size_wdg.table.rowCount() == len(mmc.getStateLabels(obj))

    assert not px_size_wdg.mag_radiobtn.isChecked()
    assert px_size_wdg.img_px_radiobtn.isChecked()

    match = table.findItems("Res40x", Qt.MatchExactly)
    row = match[0].row()

    row_1_obj = table.item(row, OBJECTIVE_LABEL).text()
    assert row_1_obj == "Nikon 40X Plan Fluor ELWD"
    row_1_cfg = table.item(row, RESOLUTION_ID).text()
    assert row_1_cfg == "Res40x"
    row_1_mag = table.item(row, MAGNIFICATION).text()
    assert row_1_mag == "40.0"
    row_1_cam_px = table.item(row, CAMERA_PX_SIZE).text()
    assert row_1_cam_px == "10.0"
    row_1_img_px = table.item(row, IMAGE_PX_SIZE)
    assert row_1_img_px.text() == "0.25"
    assert row_1_img_px.foreground().color() == QColor("magenta")

    for r in range(table.rowCount()):
        cam_px = table.item(r, CAMERA_PX_SIZE).text()
        assert cam_px == "10.0"

    # change mag
    new_mag = QTableWidgetItem("50.0")
    with qtbot.waitSignal(table.cellChanged):
        table.setItem(row, MAGNIFICATION, new_mag)
    assert table.item(row, CAMERA_PX_SIZE).text() == "10.0"
    assert table.item(row, IMAGE_PX_SIZE).text() == str(10 / 50)

    assert "Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("Res40x") == 10 / 50

    # change cam px size
    new_cam_px = QTableWidgetItem("6.0")
    with qtbot.waitSignal(table.cellChanged):
        table.setItem(row, CAMERA_PX_SIZE, new_cam_px)
    assert table.item(row, MAGNIFICATION).text() == "50.0"
    assert table.item(row, IMAGE_PX_SIZE).text() == str(6 / 50)

    assert "Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("Res40x") == 6 / 50

    # change img px size
    px_size_wdg.mag_radiobtn.setChecked(True)
    assert px_size_wdg.mag_radiobtn.isChecked()
    assert not px_size_wdg.img_px_radiobtn.isChecked()
    new_img_px = QTableWidgetItem("1.0")
    with qtbot.waitSignal(table.cellChanged):
        table.setItem(row, IMAGE_PX_SIZE, new_img_px)
        assert table.item(row, IMAGE_PX_SIZE).foreground().color() == QColor("")
    assert table.item(row, CAMERA_PX_SIZE).text() == "6.0"
    assert table.item(row, MAGNIFICATION).text() == str(6 / 1)
    assert table.item(row, MAGNIFICATION).foreground().color() == QColor("magenta")

    assert "Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("Res40x") == 1

    for r in range(table.rowCount()):
        cam_px = table.item(r, CAMERA_PX_SIZE).text()
        assert cam_px == "6.0"

    # test delete btn
    del_btn = px_size_wdg._delete_btn
    del_btn.setProperty("row", row)
    with qtbot.waitSignal(mmc.events.pixelSizeDeleted):
        del_btn.click()
    assert table.item(row, RESOLUTION_ID).text() == "None"
    assert table.item(row, MAGNIFICATION).text() == "6.0"
    assert table.item(row, CAMERA_PX_SIZE).text() == "6.0"
    assert table.item(row, IMAGE_PX_SIZE).text() == "0.0"

    assert "Res40x" not in mmc.getAvailablePixelSizeConfigs()

    # ResolutionID
    px_size_wdg.img_px_radiobtn.setChecked(True)
    assert not px_size_wdg.mag_radiobtn.isChecked()
    assert px_size_wdg.img_px_radiobtn.isChecked()
    with qtbot.waitSignal(table.cellChanged):
        table.setItem(0, RESOLUTION_ID, QTableWidgetItem("new_Res40x"))
    assert table.item(row, RESOLUTION_ID).text() == "new_Res40x"
    assert table.item(row, MAGNIFICATION).text() == "6.0"
    assert table.item(row, CAMERA_PX_SIZE).text() == "6.0"
    assert table.item(row, IMAGE_PX_SIZE).text() == "1.0"

    assert "new_Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("new_Res40x") == 1

    # pixelSizeDeleted signal
    match = table.findItems("Res10x", Qt.MatchExactly)
    row = match[0].row()
    with qtbot.waitSignal(mmc.events.pixelSizeDeleted):
        mmc.deletePixelSizeConfig("Res10x")
    assert table.item(row, RESOLUTION_ID).text() == "None"
    assert table.item(row, MAGNIFICATION).text() == "10.0"
    assert table.item(row, CAMERA_PX_SIZE).text() == "6.0"
    assert table.item(row, IMAGE_PX_SIZE).text() == "0.0"

    assert "Res10x" not in mmc.getAvailablePixelSizeConfigs()

    # pixelSizeDefined signal
    with qtbot.waitSignal(mmc.events.pixelSizeDefined):
        mmc.definePixelSizeConfig(
            "new_Res10x", "Objective", "Label", "Nikon 10X S Fluor"
        )
    assert table.item(row, RESOLUTION_ID).text() == "new_Res10x"
    assert table.item(row, MAGNIFICATION).text() == "10.0"
    assert table.item(row, CAMERA_PX_SIZE).text() == "6.0"
    assert table.item(row, IMAGE_PX_SIZE).text() == "0.0"

    assert "new_Res10x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("new_Res10x") == 0.0

    # pixelSizeSet signal
    with qtbot.waitSignal(mmc.events.pixelSizeSet):
        mmc.setPixelSizeUm("new_Res10x", 2.0)
    assert table.item(row, RESOLUTION_ID).text() == "new_Res10x"
    assert table.item(row, MAGNIFICATION).text() == str(6.0 / 2.0)
    assert table.item(row, CAMERA_PX_SIZE).text() == "6.0"
    assert table.item(row, IMAGE_PX_SIZE).text() == "2.0"
    assert mmc.getPixelSizeUmByID("new_Res10x") == 2.0
