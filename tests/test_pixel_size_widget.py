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
LABEL_STATUS = 5


def test_pixel_size_widget(qtbot: QtBot, global_mmcore: CMMCorePlus):
    mmc = global_mmcore

    px_size_wdg = PixelSizeWidget("", mmcore=mmc)
    table = px_size_wdg.table
    obj = px_size_wdg._objective_device
    m = px_size_wdg._magnification
    qtbot.addWidget(px_size_wdg)

    assert ["Res10x", "Res20x", "Res40x"] == list(mmc.getAvailablePixelSizeConfigs())
    assert px_size_wdg.table.rowCount() == len(mmc.getStateLabels(obj))

    assert not px_size_wdg.mag_radiobtn.isChecked()
    assert px_size_wdg.img_px_radiobtn.isChecked()

    assert ["Nikon 40X Plan Fluor ELWD", 40.0] in m

    match = table.findItems("Nikon 40X Plan Fluor ELWD", Qt.MatchExactly)
    row = match[0].row()

    obj = table.item(row, OBJECTIVE_LABEL).text()
    assert obj == "Nikon 40X Plan Fluor ELWD"
    resID = cast(QLineEdit, table.cellWidget(row, RESOLUTION_ID))
    assert resID.text() == "Res40x"
    assert resID.property("resID") == "Res40x"
    mag = cast(QLineEdit, table.cellWidget(row, MAGNIFICATION))
    assert mag.text() == "40.0"
    cam_px = cast(QLineEdit, table.cellWidget(row, CAMERA_PX_SIZE))
    assert cam_px.text() == "10.0"
    img_px = cast(QLineEdit, table.cellWidget(row, IMAGE_PX_SIZE))
    assert img_px.text() == "0.25"
    assert img_px.styleSheet() == "color:magenta"

    for r in range(table.rowCount()):
        _cam_px = table.cellWidget(r, CAMERA_PX_SIZE).text()
        assert _cam_px == "10.0"

    # change mag
    mag.setText("50.0")
    with qtbot.waitSignal(mag.editingFinished):
        mag.editingFinished.emit()
    assert cam_px.text() == "10.0"
    assert img_px.text() == str(10 / 50)

    assert "Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("Res40x") == 10 / 50

    assert ["Nikon 40X Plan Fluor ELWD", 50.0] in m

    # change cam px size
    cam_px.setText("6.0")
    with qtbot.waitSignal(cam_px.editingFinished):
        cam_px.editingFinished.emit()
    assert mag.text() == "50.0"
    assert img_px.text() == str(6 / 50)

    assert "Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("Res40x") == 6 / 50

    # change img px size
    px_size_wdg.mag_radiobtn.setChecked(True)
    assert px_size_wdg.mag_radiobtn.isChecked()
    assert not px_size_wdg.img_px_radiobtn.isChecked()
    img_px.setText("1.0")
    with qtbot.waitSignal(img_px.editingFinished):
        img_px.editingFinished.emit()
        assert img_px.styleSheet() == ""
    assert cam_px.text() == "6.0"
    assert mag.text() == str(6 / 1)
    assert mag.styleSheet() == "color:magenta"

    assert "Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("Res40x") == 1
    assert ["Nikon 40X Plan Fluor ELWD", 6 / 1] in m

    for r in range(table.rowCount()):
        _cam_px = table.cellWidget(r, CAMERA_PX_SIZE).text()
        assert _cam_px == "6.0"

    # test delete btn
    del_btn = px_size_wdg._delete_btn
    del_btn.setProperty("row", row)
    with qtbot.waitSignal(mmc.events.pixelSizeDeleted):
        del_btn.click()
    assert resID.text() == "None"
    assert mag.text() == "6.0"
    assert cam_px.text() == "6.0"
    assert img_px.text() == "0.0"

    assert "Res40x" not in mmc.getAvailablePixelSizeConfigs()

    # ResolutionID
    px_size_wdg.img_px_radiobtn.setChecked(True)
    assert not px_size_wdg.mag_radiobtn.isChecked()
    assert px_size_wdg.img_px_radiobtn.isChecked()
    resID.setText("new_Res40x")
    with qtbot.waitSignal(resID.editingFinished):
        resID.editingFinished.emit()
    assert resID.text() == "new_Res40x"
    assert mag.text() == "6.0"
    assert cam_px.text() == "6.0"
    assert img_px.text() == "1.0"

    assert "new_Res40x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("new_Res40x") == 1

    assert ["Nikon 40X Plan Fluor ELWD", 6.0] in m

    # pixelSizeDeleted signal
    match = table.findItems("Nikon 10X S Fluor", Qt.MatchExactly)
    row_1 = match[0].row()
    resID_1 = cast(QLineEdit, table.cellWidget(row_1, RESOLUTION_ID))
    assert resID_1.text() == "Res10x"
    mag_1 = cast(QLineEdit, table.cellWidget(row_1, MAGNIFICATION))
    cam_px_1 = cast(QLineEdit, table.cellWidget(row_1, CAMERA_PX_SIZE))
    img_px_1 = cast(QLineEdit, table.cellWidget(row_1, IMAGE_PX_SIZE))
    with qtbot.waitSignal(mmc.events.pixelSizeDeleted):
        mmc.deletePixelSizeConfig("Res10x")
    assert resID_1.text() == "None"
    assert mag_1.text() == "10.0"
    assert cam_px_1.text() == "6.0"
    assert img_px_1.text() == "0.0"

    assert "Res10x" not in mmc.getAvailablePixelSizeConfigs()

    # pixelSizeDefined signal
    with qtbot.waitSignal(mmc.events.pixelSizeDefined):
        mmc.definePixelSizeConfig(
            "new_Res10x", "Objective", "Label", "Nikon 10X S Fluor"
        )
    assert resID_1.text() == "new_Res10x"
    assert mag_1.text() == "10.0"
    assert cam_px_1.text() == "6.0"
    assert img_px_1.text() == "0.0"

    assert "new_Res10x" in mmc.getAvailablePixelSizeConfigs()
    assert mmc.getPixelSizeUmByID("new_Res10x") == 0.0

    assert ["Nikon 10X S Fluor", 10.0] in m

    # pixelSizeSet signal
    with qtbot.waitSignal(mmc.events.pixelSizeSet):
        mmc.setPixelSizeUm("new_Res10x", 2.0)
    assert resID_1.text() == "new_Res10x"
    assert mag_1.text() == str(6.0 / 2.0)
    assert cam_px_1.text() == "6.0"
    assert img_px_1.text() == "2.0"
    assert mmc.getPixelSizeUmByID("new_Res10x") == 2.0
