from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus

from pymmcore_widgets._pixel_size_widget import PixelSizeTable, PixelSizeWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot
    from qtpy.QtWidgets import QWidget


OBJECTIVE_LABEL = 0
RESOLUTION_ID = 1
CAMERA_PX_SIZE = 2
MAGNIFICATION = 3
IMAGE_PX_SIZE = 4
ROW = 0  # "Nikon 40X Plan Fluor ELWD"


def _get_wdg(table: PixelSizeTable) -> tuple[str, QWidget, QWidget, QWidget, QWidget]:
    obj = table.item(ROW, OBJECTIVE_LABEL).text()
    resID = table.cellWidget(ROW, RESOLUTION_ID)
    mag = table.cellWidget(ROW, MAGNIFICATION)
    cam_px = table.cellWidget(ROW, CAMERA_PX_SIZE)
    img_px = table.cellWidget(ROW, IMAGE_PX_SIZE)
    return obj, resID, mag, cam_px, img_px


def test_pixel_size_table(qtbot: QtBot):
    mmc = CMMCorePlus.instance()
    px_size_wdg = PixelSizeWidget()
    table = px_size_wdg.table
    obj = px_size_wdg.objective_device
    qtbot.addWidget(px_size_wdg)

    assert ["Res10x", "Res20x", "Res40x"] == list(mmc.getAvailablePixelSizeConfigs())
    assert table.rowCount() == len(mmc.getStateLabels(obj))

    assert not px_size_wdg.mag_radiobtn.isChecked()
    assert px_size_wdg.img_px_radiobtn.isChecked()

    obj, resID, mag, cam_px, img_px = _get_wdg(table)

    assert obj == "Nikon 40X Plan Fluor ELWD"
    assert resID.text() == "Res40x"
    assert resID.property("resID") == "Res40x"
    assert resID.graphicsEffect().opacity() == 1.00
    assert mag.text() == "40.0"
    assert mag.graphicsEffect().opacity() == 1.00
    assert cam_px.text() == "10.00"
    assert cam_px.graphicsEffect().opacity() == 1.00
    assert img_px.text() == "0.2500"
    assert img_px.graphicsEffect().opacity() == 1.00
    assert img_px.styleSheet() == "color:magenta"

    for r in range(table.rowCount()):
        _cam_px = table.cellWidget(r, CAMERA_PX_SIZE).text()
        assert _cam_px == "10.00"


def test_change_magnification(qtbot: QtBot):
    mmc = CMMCorePlus.instance()
    px_size_wdg = PixelSizeWidget()
    qtbot.addWidget(px_size_wdg)
    table = px_size_wdg.table

    _, _, mag, cam_px, img_px = _get_wdg(table)

    mag.setText("50.0")
    with qtbot.waitSignal(mag.editingFinished):
        mag.editingFinished.emit()
    _, _, _, cam_px, img_px = _get_wdg(table)
    assert cam_px.text() == "10.00"
    assert img_px.text() == f"{(10 / 50):.4f}"
    assert "Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("Res40x") == 10 / 50


def test_change_cam_pixel_size(qtbot: QtBot):
    mmc = CMMCorePlus.instance()
    px_size_wdg = PixelSizeWidget()
    qtbot.addWidget(px_size_wdg)
    table = px_size_wdg.table

    _, _, mag, cam_px, img_px = _get_wdg(table)

    cam_px.setText("6.00")
    cam_px.editingFinished.emit()
    with qtbot.waitSignal(cam_px.editingFinished):
        cam_px.editingFinished.emit()
    _, _, mag, cam_px, img_px = _get_wdg(table)
    assert mag.text() == "40.0"
    assert img_px.text() == f"{(6 / 40):.4f}"
    assert "Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("Res40x") == 6 / 40
    assert table.cellWidget(ROW + 1, CAMERA_PX_SIZE).text() == "6.00"


def test_change_img_pixel_size(qtbot: QtBot):
    mmc = CMMCorePlus.instance()
    px_size_wdg = PixelSizeWidget()
    qtbot.addWidget(px_size_wdg)
    table = px_size_wdg.table

    _, _, mag, cam_px, img_px = _get_wdg(table)

    px_size_wdg.mag_radiobtn.setChecked(True)
    assert px_size_wdg.mag_radiobtn.isChecked()
    assert not px_size_wdg.img_px_radiobtn.isChecked()
    img_px.setText("1.0000")
    with qtbot.waitSignal(img_px.editingFinished):
        img_px.editingFinished.emit()
        assert img_px.styleSheet() == ""
    _, _, mag, cam_px, img_px = _get_wdg(table)
    assert cam_px.text() == "10.00"
    assert mag.text() == str(10 / 1)
    assert mag.styleSheet() == "color:magenta"
    assert "Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("Res40x") == 1

    for r in range(table.rowCount()):
        _cam_px = table.cellWidget(r, CAMERA_PX_SIZE).text()
        assert _cam_px == "10.00"


def test_ResolutionID(qtbot: QtBot):
    mmc = CMMCorePlus.instance()
    px_size_wdg = PixelSizeWidget()
    qtbot.addWidget(px_size_wdg)
    table = px_size_wdg.table

    px_size_wdg.img_px_radiobtn.setChecked(True)
    assert not px_size_wdg.mag_radiobtn.isChecked()
    assert px_size_wdg.img_px_radiobtn.isChecked()
    _, resID, _, _, _ = _get_wdg(table)
    assert resID.property("resID") == "Res40x"
    assert resID.text() in mmc.getAvailablePixelSizeConfigs()
    resID.setText("new_Res40x")
    with qtbot.waitSignal(resID.editingFinished):
        resID.editingFinished.emit()
    _, resID, mag, cam_px, img_px = _get_wdg(table)
    assert resID.text() == "new_Res40x"
    assert resID.property("resID") == "new_Res40x"
    assert mag.text() == "40.0"
    assert cam_px.text() == "10.00"
    assert img_px.text() == "0.2500"
    assert "Res40x" not in mmc.getAvailablePixelSizeConfigs()
    assert "new_Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("new_Res40x") == 0.25
    assert resID.graphicsEffect().opacity() == 1.00
    assert mag.graphicsEffect().opacity() == 1.00
    assert cam_px.graphicsEffect().opacity() == 1.00
    assert img_px.graphicsEffect().opacity() == 1.00


def test_delete_button(qtbot: QtBot):
    mmc = CMMCorePlus.instance()
    px_size_wdg = PixelSizeWidget()
    qtbot.addWidget(px_size_wdg)
    table = px_size_wdg.table

    del_btn = table.cellWidget(ROW, 5).children()[-1]
    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        del_btn.click()
    _, resID, mag, cam_px, img_px = _get_wdg(table)
    assert resID.text() == "None"
    assert mag.text() == "40.0"
    assert cam_px.text() == "10.00"
    assert img_px.text() == "0.0000"
    assert "Res40x" not in mmc.getAvailablePixelSizeConfigs()
    assert resID.graphicsEffect().opacity() == 0.50
    assert mag.graphicsEffect().opacity() == 0.50
    assert cam_px.graphicsEffect().opacity() == 0.50
    assert img_px.graphicsEffect().opacity() == 0.50


def test_setPixelSizeUm(qtbot: QtBot):
    mmc = CMMCorePlus.instance()
    px_size_wdg = PixelSizeWidget()
    qtbot.addWidget(px_size_wdg)
    table = px_size_wdg.table

    _, _, _, _, img_px = _get_wdg(table)
    assert img_px.text() == "0.2500"

    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        mmc.setPixelSizeUm("Res40x", 0.0)
    _, resID, mag, cam_px, img_px = _get_wdg(table)
    assert mag.text() == "40.0"
    assert cam_px.text() == "10.00"
    assert img_px.text() == "0.0000"
    assert resID.graphicsEffect().opacity() == 0.50
    assert mag.graphicsEffect().opacity() == 0.50
    assert cam_px.graphicsEffect().opacity() == 0.50
    assert img_px.graphicsEffect().opacity() == 0.50

    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        mmc.setPixelSizeUm("Res40x", 0.2500)
    _, resID, mag, cam_px, img_px = _get_wdg(table)
    assert mag.text() == "40.0"
    assert cam_px.text() == "10.00"
    assert img_px.text() == "0.2500"
    assert resID.graphicsEffect().opacity() == 1.00
    assert mag.graphicsEffect().opacity() == 1.00
    assert cam_px.graphicsEffect().opacity() == 1.00
    assert img_px.graphicsEffect().opacity() == 1.00


def test_deletePixelSizeConfig(qtbot: QtBot):
    mmc = CMMCorePlus.instance()
    px_size_wdg = PixelSizeWidget()
    qtbot.addWidget(px_size_wdg)
    table = px_size_wdg.table

    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        mmc.deletePixelSizeConfig("Res40x")
    _, resID, mag, cam_px, img_px = _get_wdg(table)
    assert resID.text() == "None"
    assert resID.property("resID") == "None"
    assert mag.text() == "40.0"
    assert cam_px.text() == "10.00"
    assert img_px.text() == "0.0000"
    assert "Res40x" not in mmc.getAvailablePixelSizeConfigs()
    assert resID.graphicsEffect().opacity() == 0.50
    assert mag.graphicsEffect().opacity() == 0.50
    assert cam_px.graphicsEffect().opacity() == 0.50
    assert img_px.graphicsEffect().opacity() == 0.50


def test_definePixelSizeConfig(qtbot: QtBot):
    mmc = CMMCorePlus.instance()
    px_size_wdg = PixelSizeWidget()
    qtbot.addWidget(px_size_wdg)
    table = px_size_wdg.table

    del_btn = table.cellWidget(ROW, 5).children()[-1]
    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        del_btn.click()

    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        mmc.definePixelSizeConfig(
            "Res40x_new", "Objective", "Label", "Nikon 40X Plan Fluor ELWD"
        )
    _, resID, mag, cam_px, img_px = _get_wdg(table)
    assert "Res40x_new" in mmc.getAvailablePixelSizeConfigs()
    assert resID.text() == "Res40x_new"
    assert resID.property("resID") == "Res40x_new"
    assert mag.text() == "40.0"
    assert cam_px.text() == "10.00"
    assert img_px.text() == "0.0000"
    assert resID.graphicsEffect().opacity() == 0.50
    assert mag.graphicsEffect().opacity() == 0.50
    assert cam_px.graphicsEffect().opacity() == 0.50
    assert img_px.graphicsEffect().opacity() == 0.50
