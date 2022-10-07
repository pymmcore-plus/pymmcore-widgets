from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLineEdit

from pymmcore_widgets._pixel_size_widget import PixelSizeWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


OBJECTIVE_LABEL = 0
RESOLUTION_ID = 1
CAMERA_PX_SIZE = 2
MAGNIFICATION = 3
IMAGE_PX_SIZE = 4


def test_pixel_size_widget(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore

    px_size_wdg = PixelSizeWidget()
    table = px_size_wdg.table
    obj = px_size_wdg.objective_device
    qtbot.addWidget(px_size_wdg)

    assert ["Res10x", "Res20x", "Res40x"] == list(mmc.getAvailablePixelSizeConfigs())
    assert px_size_wdg.table.rowCount() == len(mmc.getStateLabels(obj))

    assert not px_size_wdg.mag_radiobtn.isChecked()
    assert px_size_wdg.img_px_radiobtn.isChecked()

    match = table.findItems("Nikon 40X Plan Fluor ELWD", Qt.MatchExactly)
    row = match[0].row()

    def _get_wdg(row: int):
        obj = table.item(row, OBJECTIVE_LABEL).text()
        resID = cast(QLineEdit, table.cellWidget(row, RESOLUTION_ID))
        mag = cast(QLineEdit, table.cellWidget(row, MAGNIFICATION))
        cam_px = cast(QLineEdit, table.cellWidget(row, CAMERA_PX_SIZE))
        img_px = cast(QLineEdit, table.cellWidget(row, IMAGE_PX_SIZE))
        return obj, resID, mag, cam_px, img_px

    obj, resID, mag, cam_px, img_px = _get_wdg(row)
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

    # change mag
    mag.setText("50.0")
    with qtbot.waitSignals([mag.editingFinished, mmc.events.pixelSizeChanged]):
        mag.editingFinished.emit()
    _, _, _, cam_px, img_px = _get_wdg(row)
    assert cam_px.text() == "10.00"
    assert img_px.text() == f"{(10 / 50):.4f}"
    assert "Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("Res40x") == 10 / 50

    # change cam px size
    _, _, mag, cam_px, img_px = _get_wdg(row)
    cam_px.setText("6.00")
    cam_px.editingFinished.emit()
    with qtbot.waitSignal(cam_px.editingFinished):
        cam_px.editingFinished.emit()
    _, _, mag, cam_px, img_px = _get_wdg(row)
    assert mag.text() == "50.0"
    assert img_px.text() == f"{(6 / 50):.4f}"
    assert "Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("Res40x") == 6 / 50
    assert table.cellWidget(row + 1, CAMERA_PX_SIZE).text() == "6.00"

    # change img px size
    _, _, mag, cam_px, img_px = _get_wdg(row)
    px_size_wdg.mag_radiobtn.setChecked(True)
    assert px_size_wdg.mag_radiobtn.isChecked()
    assert not px_size_wdg.img_px_radiobtn.isChecked()
    img_px.setText("1.0000")
    with qtbot.waitSignals([img_px.editingFinished, mmc.events.pixelSizeChanged]):
        img_px.editingFinished.emit()
        assert img_px.styleSheet() == ""
    _, _, mag, cam_px, img_px = _get_wdg(row)
    assert cam_px.text() == "6.00"
    assert mag.text() == str(6 / 1)
    assert mag.styleSheet() == "color:magenta"
    assert "Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("Res40x") == 1

    for r in range(table.rowCount()):
        _cam_px = table.cellWidget(r, CAMERA_PX_SIZE).text()
        assert _cam_px == "6.00"

    # test delete btn
    del_btn = table.cellWidget(row, 5).children()[-1]
    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        del_btn.click()
    _, resID, mag, cam_px, img_px = _get_wdg(row)
    assert resID.text() == "None"
    assert mag.text() == "6.0"
    assert cam_px.text() == "6.00"
    assert img_px.text() == "0.0000"
    assert "Res40x" not in mmc.getAvailablePixelSizeConfigs()
    assert resID.graphicsEffect().opacity() == 0.50
    assert mag.graphicsEffect().opacity() == 0.50
    assert cam_px.graphicsEffect().opacity() == 0.50
    assert img_px.graphicsEffect().opacity() == 0.50

    # ResolutionID
    px_size_wdg.img_px_radiobtn.setChecked(True)
    assert not px_size_wdg.mag_radiobtn.isChecked()
    assert px_size_wdg.img_px_radiobtn.isChecked()
    _, resID, _, _, _ = _get_wdg(row)
    assert resID.property("resID") == "None"
    resID.setText("new_Res40x")
    with qtbot.waitSignals([resID.editingFinished, mmc.events.pixelSizeChanged]):
        resID.editingFinished.emit()
    _, resID, mag, cam_px, img_px = _get_wdg(row)
    assert resID.text() == "new_Res40x"
    assert resID.property("resID") == "new_Res40x"
    assert mag.text() == "6.0"
    assert cam_px.text() == "6.00"
    assert img_px.text() == "1.0000"
    assert "new_Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("new_Res40x") == 1
    assert resID.graphicsEffect().opacity() == 1.00
    assert mag.graphicsEffect().opacity() == 1.00
    assert cam_px.graphicsEffect().opacity() == 1.00
    assert img_px.graphicsEffect().opacity() == 1.00

    # test mmc.events.pixelSizeChanged
    match = table.findItems("Nikon 10X S Fluor", Qt.MatchExactly)
    row_1 = match[0].row()
    obj, resID, mag, cam_px, img_px = _get_wdg(row_1)
    assert obj == "Nikon 10X S Fluor"
    assert resID.text() == "Res10x"
    assert resID.property("resID") == "Res10x"
    assert mag.text() == "10.0"
    assert cam_px.text() == "6.00"
    assert img_px.text() == "0.6000"
    assert img_px.styleSheet() == "color:magenta"

    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        mmc.deletePixelSizeConfig("Res10x")
    _, resID, mag, cam_px, img_px = _get_wdg(row_1)
    assert resID.text() == "None"
    assert resID.property("resID") == "None"
    assert mag.text() == "10.0"
    assert cam_px.text() == "6.00"
    assert img_px.text() == "0.0000"
    assert "Res10x" not in mmc.getAvailablePixelSizeConfigs()
    assert resID.graphicsEffect().opacity() == 0.50
    assert mag.graphicsEffect().opacity() == 0.50
    assert cam_px.graphicsEffect().opacity() == 0.50
    assert img_px.graphicsEffect().opacity() == 0.50

    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        mmc.definePixelSizeConfig(
            "Res10x_new", "Objective", "Label", "Nikon 10X S Fluor"
        )
    _, resID, mag, cam_px, img_px = _get_wdg(row_1)
    assert "Res10x_new" in mmc.getAvailablePixelSizeConfigs()
    assert resID.text() == "Res10x_new"
    assert resID.property("resID") == "Res10x_new"
    assert mag.text() == "10.0"
    assert cam_px.text() == "6.00"
    assert img_px.text() == "0.0000"
    assert resID.graphicsEffect().opacity() == 0.50
    assert mag.graphicsEffect().opacity() == 0.50
    assert cam_px.graphicsEffect().opacity() == 0.50
    assert img_px.graphicsEffect().opacity() == 0.50

    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        mmc.setPixelSizeUm("Res10x_new", 1.0)
    _, resID, mag, cam_px, img_px = _get_wdg(row_1)
    assert mag.text() == "6.0"
    assert cam_px.text() == "6.00"
    assert img_px.text() == "1.0000"
    assert resID.graphicsEffect().opacity() == 1.00
    assert mag.graphicsEffect().opacity() == 1.00
    assert cam_px.graphicsEffect().opacity() == 1.00
    assert img_px.graphicsEffect().opacity() == 1.00
