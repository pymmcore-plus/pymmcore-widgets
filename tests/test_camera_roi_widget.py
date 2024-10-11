from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, call

from pymmcore_plus import CMMCorePlus

from pymmcore_widgets.control._camera_roi_widget import CameraRoiWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

FULL = "Full Chip"
CUSTOM_ROI = "Custom ROI"


def _get_wdgs(cam_wdg: CameraRoiWidget):
    cam_x = cam_wdg.start_x  # QSpinbox
    cam_y = cam_wdg.start_y  # QSpinbox
    w = cam_wdg.roi_width  # QSpinbox
    h = cam_wdg.roi_height  # QSpinbox
    combo = cam_wdg.cam_roi_combo  # QComboBox
    cbox = cam_wdg.center_checkbox  # QCheckBox
    crop = cam_wdg.crop_btn  # QPushButton
    return cam_x, cam_y, w, h, combo, cbox, crop


def test_load_camera_roi_widget(qtbot: QtBot):
    cam = CameraRoiWidget()
    qtbot.addWidget(cam)

    cam_x, cam_y, w, h, combo, cbox, _ = _get_wdgs(cam)

    assert cam_x.value() == 0
    assert cam_y.value() == 0
    assert w.value() == 512
    assert h.value() == 512
    assert cbox.isChecked()

    items = [FULL, CUSTOM_ROI, "64 x 64", "85 x 85", "128 x 128", "256 x 256"]
    combo_items = [combo.itemText(i) for i in range(combo.count())]
    assert items == combo_items


def test_camera_roi_combo(qtbot: QtBot):
    mmc = CMMCorePlus.instance()
    cam = CameraRoiWidget()
    qtbot.addWidget(cam)

    cam_x, cam_y, w, h, combo, cbox, _ = _get_wdgs(cam)

    combo.setCurrentText("256 x 256")
    assert not cam_x.isEnabled()
    assert not cam_y.isEnabled()
    assert not w.isEnabled()
    assert not h.isEnabled()
    assert cam_x.value() == 128
    assert cam_y.value() == 128
    assert w.value() == 256
    assert h.value() == 256
    assert cbox.isChecked()
    assert cam.lbl_info.text() == "Size: 256 px * 256 px [256.0 µm * 256.0 µm]"
    assert not cam.lbl_info.styleSheet()
    assert mmc.getROI() == [128, 128, 256, 256]

    combo.setCurrentText(FULL)
    assert not cam_x.isEnabled()
    assert not cam_y.isEnabled()
    assert not w.isEnabled()
    assert not h.isEnabled()
    assert cam_x.value() == 0
    assert cam_y.value() == 0
    assert w.value() == 512
    assert h.value() == 512
    assert cbox.isChecked()
    assert cam.lbl_info.text() == "Size: 512 px * 512 px [512.0 µm * 512.0 µm]"
    assert not cam.lbl_info.styleSheet()
    assert mmc.getROI() == [0, 0, 512, 512]


def test_camera_roi_combo_custom(qtbot: QtBot):
    mmc = CMMCorePlus.instance()
    cam = CameraRoiWidget()
    qtbot.addWidget(cam)

    cam_x, cam_y, w, h, combo, cbox, crop = _get_wdgs(cam)

    mock_1 = Mock()
    cam.roiChanged.connect(mock_1)

    combo.setCurrentText(FULL)
    combo.setCurrentText(CUSTOM_ROI)
    assert cam_x.isEnabled()
    assert cam_y.isEnabled()
    assert w.isEnabled()
    assert h.isEnabled()
    assert cam_x.value() == 0
    assert cam_y.value() == 0
    assert w.value() == 512
    assert h.value() == 512
    assert not cbox.isChecked()
    assert cam.lbl_info.text() == "Size: 512 px * 512 px [512.0 µm * 512.0 µm]"
    assert not cam.lbl_info.styleSheet()
    assert mmc.getROI() == [0, 0, 512, 512]

    w.setValue(200)
    h.setValue(210)
    cam_x.setValue(100)
    cam_y.setValue(130)

    assert cam_x.value() == 100
    assert cam_y.value() == 130
    assert cam.lbl_info.text() == "Size: 200 px * 210 px [200.0 µm * 210.0 µm]"
    assert cam.lbl_info.styleSheet() == "color: magenta;"
    assert mmc.getROI() == [0, 0, 512, 512]

    crop.click()
    assert mmc.getROI() == [100, 130, 200, 210]
    assert cam.lbl_info.text() == "Size: 200 px * 210 px [200.0 µm * 210.0 µm]"
    assert not cam.lbl_info.styleSheet()

    w.setValue(201)
    assert cam.lbl_info.text() == "Size: 201 px * 210 px [201.0 µm * 210.0 µm]"
    assert cam.lbl_info.styleSheet() == "color: magenta;"
    assert mmc.getROI() == [0, 0, 512, 512]


def test_camera_roi_widget_signal(qtbot: QtBot):
    cam = CameraRoiWidget()
    qtbot.addWidget(cam)

    cam_x, cam_y, w, h, combo, cbox, _ = _get_wdgs(cam)

    mock_1 = Mock()
    cam.roiChanged.connect(mock_1)

    combo.setCurrentText(FULL)
    combo.setCurrentText(CUSTOM_ROI)
    assert cam.lbl_info.text() == "Size: 512 px * 512 px [512.0 µm * 512.0 µm]"
    assert not cam.lbl_info.styleSheet()

    w.setValue(200)
    mock_1.assert_has_calls([call(0, 0, 200, 512, CUSTOM_ROI)])
    assert cam.lbl_info.text() == "Size: 200 px * 512 px [200.0 µm * 512.0 µm]"
    assert cam.lbl_info.styleSheet() == "color: magenta;"

    h.setValue(300)
    mock_1.assert_has_calls([call(0, 0, 200, 300, CUSTOM_ROI)])
    assert cam.lbl_info.text() == "Size: 200 px * 300 px [200.0 µm * 300.0 µm]"
    assert cam.lbl_info.styleSheet() == "color: magenta;"

    cam_x.setValue(50)
    mock_1.assert_has_calls([call(50, 0, 200, 300, CUSTOM_ROI)])
    assert cam.lbl_info.text() == "Size: 200 px * 300 px [200.0 µm * 300.0 µm]"
    assert cam.lbl_info.styleSheet() == "color: magenta;"

    cam_y.setValue(30)
    mock_1.assert_has_calls([call(50, 30, 200, 300, CUSTOM_ROI)])
    assert cam.lbl_info.text() == "Size: 200 px * 300 px [200.0 µm * 300.0 µm]"
    assert cam.lbl_info.styleSheet() == "color: magenta;"

    cbox.setChecked(True)
    mock_1.assert_has_calls([call(156, 106, 200, 300, CUSTOM_ROI)])
    assert cam.lbl_info.text() == "Size: 200 px * 300 px [200.0 µm * 300.0 µm]"
    assert cam.lbl_info.styleSheet() == "color: magenta;"
    assert not cam_x.isEnabled()
    assert not cam_y.isEnabled()
    assert w.isEnabled()
    assert h.isEnabled()
    assert cam_x.value() == 156
    assert cam_y.value() == 106
    assert w.value() == 200
    assert h.value() == 300


def test_core_setROI(qtbot: QtBot):
    mmc = CMMCorePlus.instance()
    cam = CameraRoiWidget()
    qtbot.addWidget(cam)

    cam_x, cam_y, w, h, combo, cbox, _ = _get_wdgs(cam)

    mock_2 = Mock()
    mmc.events.roiSet.connect(mock_2)

    combo.setCurrentText(FULL)

    mmc.setROI(10, 10, 100, 100)
    assert mmc.getROI() == [10, 10, 100, 100]
    assert combo.currentText() == CUSTOM_ROI
    assert cam_x.isEnabled()
    assert cam_y.isEnabled()
    assert w.isEnabled()
    assert h.isEnabled()
    mock_2.assert_has_calls([call("Camera", 10, 10, 100, 100)])
