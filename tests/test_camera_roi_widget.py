from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, call

from pymmcore_plus import CMMCorePlus

from pymmcore_widgets._camera_roi_widget import CameraRoiWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_camera_roi_widget(global_mmcore: CMMCorePlus, qtbot: QtBot):
    cam = CameraRoiWidget()
    qtbot.addWidget(cam)
    mmc = global_mmcore

    mock_1 = Mock()
    cam.roiInfo.connect(mock_1)
    mock_2 = Mock()
    mmc.events.roiSet.connect(mock_2)

    cam_x = cam.start_x  # QSpinbox
    cam_y = cam.start_y  # QSpinbox
    w = cam.roi_width  # QSpinbox
    h = cam.roi_height  # QSpinbox
    combo = cam.cam_roi_combo  # QComboBox
    cbox = cam.center_checkbox  # QCheckBox
    crop = cam.crop_btn  # QPushButton

    assert cam_x.value() == 0
    assert cam_y.value() == 0
    assert w.value() == 512
    assert h.value() == 512
    assert cbox.isChecked()

    items = ["Full", "ROI", "64 x 64", "85 x 85", "128 x 128", "256 x 256"]
    combo_items = [combo.itemText(i) for i in range(combo.count())]
    assert items == combo_items

    combo.setCurrentText("256 x 256")
    mock_1.assert_has_calls(
        [call(cam_x.value(), cam_y.value(), w.value(), h.value(), "256 x 256")]
    )
    assert not cam_x.isEnabled()
    assert not cam_y.isEnabled()
    assert not w.isEnabled()
    assert not h.isEnabled()
    assert cam_x.value() == 128
    assert cam_y.value() == 128
    assert w.value() == 256
    assert h.value() == 256
    assert cbox.isChecked()

    mmc.setROI(10, 10, 100, 100)
    mock_2.assert_has_calls([call("Camera", 10, 10, 100, 100)])
    mock_1.assert_has_calls([call(10, 10, 100, 100, "ROI")])

    _, _, width, height = mmc.getROI("Camera")
    assert width == 100
    assert height == 100

    assert combo.currentText() == "ROI"
    assert cam_x.isEnabled()
    assert cam_y.isEnabled()
    assert w.isEnabled()
    assert h.isEnabled()
    assert cam_x.value() == 10
    assert cam_y.value() == 10
    assert w.value() == 100
    assert h.value() == 100
    assert not cbox.isChecked()

    cam_x.setValue(50)
    mock_1.assert_has_calls([call(50, 10, 100, 100, "ROI")])

    cam_y.setValue(30)
    mock_1.assert_has_calls([call(50, 30, 100, 100, "ROI")])

    w.setValue(200)
    mock_1.assert_has_calls([call(50, 30, 200, 100, "ROI")])

    h.setValue(300)
    mock_1.assert_has_calls([call(50, 30, 200, 300, "ROI")])

    cbox.setChecked(True)
    mock_1.assert_has_calls([call(156, 106, 200, 300, "ROI")])
    assert not cam_x.isEnabled()
    assert not cam_y.isEnabled()
    assert w.isEnabled()
    assert h.isEnabled()
    assert cam_x.value() == 156
    assert cam_y.value() == 106
    assert w.value() == 200
    assert h.value() == 300

    crop.click()

    mock_2.assert_has_calls([call("Camera", 156, 106, 200, 300)])
    mock_1.assert_has_calls([call(156, 106, 200, 300, "ROI")])
    _, _, width, height = mmc.getROI("Camera")
    assert width == 200
    assert height == 300
