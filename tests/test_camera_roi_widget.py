from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, call

import pytest

from pymmcore_widgets.control._camera_roi_widget import (
    CUSTOM_ROI,
    FULL,
    ROI,
    CameraInfo,
    CameraRoiWidget,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytestqt.qtbot import QtBot

TEST_CONFIG = str(Path(__file__).parent / "test_config.cfg")

to_add = """
Property,Core,Initialize,0

Device,Multi Camera,Utilities,Multi Camera
Device,DHub_1,DemoCamera,DHub
Device,Camera1,DemoCamera,DCam
Device,DHub_2,DemoCamera,DHub
Device,Camera2,DemoCamera,DCam

Property,Camera1,MaximumExposureMs,10000.0000
Property,Camera2,MaximumExposureMs,10000.0000

Parent,Camera1,DHub_1
Parent,Camera2,DHub_2
"""


@pytest.fixture
def multi_cam_cfg() -> Generator[Path, None, None]:
    """Create a test config file with 3 cameras and a Multi Camera device."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        test_config = tmp_dir_path / "multi_cam_test.cfg"
        shutil.copy(Path(TEST_CONFIG), test_config)

        # update the test config file by adding two more cameras and a Multi Camera
        txt = test_config.read_text().strip()
        txt = txt.replace("Property,Core,Initialize,0", to_add)

        with test_config.open("w") as f:
            f.write(txt)

        yield test_config


def _get_wdgs(cam_wdg: CameraRoiWidget):
    cam_combo = cam_wdg.camera_combo  # QComboBox
    roi_combo = cam_wdg.camera_roi_combo  # QComboBox
    x = cam_wdg.start_x  # QSpinbox
    y = cam_wdg.start_y  # QSpinbox
    w = cam_wdg.roi_width  # QSpinbox
    h = cam_wdg.roi_height  # QSpinbox
    cbox = cam_wdg.center_checkbox  # QCheckBox
    crop = cam_wdg.crop_btn  # QPushButton
    snap = cam_wdg.snap_checkbox  # QPushButton
    return cam_combo, roi_combo, x, y, w, h, cbox, snap, crop


def test_load_camera_roi_widget(qtbot: QtBot, multi_cam_cfg: Path):
    cam = CameraRoiWidget()
    qtbot.addWidget(cam)
    mmc = cam._mmc
    mmc.loadSystemConfiguration(multi_cam_cfg)

    cam_combo, roi_combo, x, y, w, h, cbox, snap, crop = _get_wdgs(cam)

    rois = [roi_combo.itemText(i) for i in range(roi_combo.count())]
    assert rois == [FULL, CUSTOM_ROI, "64 x 64", "85 x 85", "128 x 128", "256 x 256"]

    cameras = [cam_combo.itemText(i) for i in range(cam_combo.count())]
    assert any(c in cameras for c in ["Camera", "Camera1", "Camera2"])

    assert mmc.getCameraDevice() == "Camera"
    assert cam.camera == "Camera"

    assert roi_combo.currentText() == FULL
    assert not cam._custom_roi_wdg.isEnabled()
    assert x.value() == 0
    assert y.value() == 0
    assert w.value() == 512
    assert h.value() == 512
    assert cbox.isChecked()
    assert not snap.isHidden()
    assert not snap.isChecked()
    assert not crop.isEnabled()

    assert cam.lbl_info.text() == "Size: 512 px * 512 px [512.0 µm * 512.0 µm]"
    assert not cam.lbl_info.styleSheet()

    cams_info = {
        "Camera": CameraInfo(
            pixel_width=512,
            pixel_height=512,
            crop_mode=FULL,
            roi=ROI(x=0, y=0, w=512, h=512, centered=True),
        ),
        "Camera1": CameraInfo(
            pixel_width=512,
            pixel_height=512,
            crop_mode=FULL,
            roi=ROI(x=0, y=0, w=512, h=512, centered=True),
        ),
        "Camera2": CameraInfo(
            pixel_width=512,
            pixel_height=512,
            crop_mode=FULL,
            roi=ROI(x=0, y=0, w=512, h=512, centered=True),
        ),
    }

    assert cam.value() == cams_info


def test_preset_crop_mode(qtbot: QtBot, multi_cam_cfg: Path):
    cam = CameraRoiWidget()
    qtbot.addWidget(cam)
    mmc = cam._mmc
    mmc.loadSystemConfiguration(multi_cam_cfg)
    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        mmc.setConfig("Objective", "20X")

    assert cam.camera == mmc.getCameraDevice() == "Camera"

    # change camera to Camera1
    cam.camera_combo.setCurrentText("Camera1")
    # default core camera should not change
    assert mmc.getCameraDevice() == "Camera"
    assert cam.camera_roi_combo.currentText() == FULL
    assert cam.lbl_info.text() == "Size: 512 px * 512 px [256.0 µm * 256.0 µm]"
    assert not cam.lbl_info.styleSheet()

    cam.camera_roi_combo.setCurrentText("256 x 256")

    assert mmc.getROI("Camera1") == [128, 128, 256, 256]

    _, _, x, y, w, h, cbox, snap, crop = _get_wdgs(cam)
    assert not cam._custom_roi_wdg.isEnabled()
    assert x.value() == 128
    assert y.value() == 128
    assert w.value() == 256
    assert h.value() == 256
    assert cbox.isChecked()
    assert snap.isHidden()
    assert not crop.isEnabled()
    assert cam.lbl_info.text() == "Size: 256 px * 256 px [128.0 µm * 128.0 µm]"
    assert not cam.lbl_info.styleSheet()

    assert cam.value()["Camera1"].roi == ROI(x=128, y=128, w=256, h=256, centered=True)
    assert cam.value()["Camera1"].crop_mode == "256 x 256"

    assert cam.value()["Camera1"] == CameraInfo(
        pixel_width=512,
        pixel_height=512,
        crop_mode="256 x 256",
        roi=ROI(x=128, y=128, w=256, h=256, centered=True),
    )


def test_custom_crop_mode(qtbot: QtBot, multi_cam_cfg: Path):
    cam = CameraRoiWidget()
    qtbot.addWidget(cam)
    mmc = cam._mmc
    mmc.loadSystemConfiguration(multi_cam_cfg)
    with qtbot.waitSignal(mmc.events.pixelSizeChanged):
        mmc.setConfig("Objective", "40X")

    assert cam.camera == mmc.getCameraDevice() == "Camera"

    # change camera to Camera2
    cam.camera_combo.setCurrentText("Camera2")
    # default core camera should not change
    assert mmc.getCameraDevice() == "Camera"
    assert cam.camera_roi_combo.currentText() == FULL
    assert cam.lbl_info.text() == "Size: 512 px * 512 px [128.0 µm * 128.0 µm]"
    assert not cam.lbl_info.styleSheet()

    # set the crop mode to CUSTOM_ROI
    cam.camera_roi_combo.setCurrentText(CUSTOM_ROI)

    _, _, x, y, w, h, cbox, snap, crop = _get_wdgs(cam)
    assert snap.isHidden()
    assert cbox.isChecked()
    assert crop.isEnabled()

    # change the camera ROI with centered=True
    w.setValue(500)
    h.setValue(412)
    assert cbox.isChecked()
    assert not x.isEnabled()
    assert not y.isEnabled()
    assert x.value() == 6  # 512 - 500 // 2
    assert y.value() == 50  # 512 - 412 // 2
    assert x.maximum() == 12  # 512 - 500
    assert y.maximum() == 100  # 512 - 412
    assert cam.lbl_info.text() == "Size: 500 px * 412 px [125.0 µm * 103.0 µm]"
    assert cam.lbl_info.styleSheet() == "color: magenta;"

    # without pressing the crop button, the stored roi should not change
    assert cam.value()["Camera2"].roi == ROI(x=0, y=0, w=512, h=512, centered=True)
    assert cam.value()["Camera2"].crop_mode == FULL
    assert mmc.getROI("Camera2") == [0, 0, 512, 512]

    with qtbot.waitSignal(mmc.events.roiSet):
        crop.click()

    assert cam.value()["Camera2"].roi == ROI(x=6, y=50, w=500, h=412, centered=True)
    assert cam.value()["Camera2"].crop_mode == CUSTOM_ROI
    assert mmc.getROI("Camera2") == [6, 50, 500, 412]
    assert not cam.lbl_info.styleSheet()

    # change the camera ROI with centered=False
    cbox.setChecked(False)
    w.setValue(412)
    assert cam.lbl_info.text() == "Size: 412 px * 412 px [103.0 µm * 103.0 µm]"
    assert cam.lbl_info.styleSheet() == "color: magenta;"
    assert mmc.getROI("Camera2") == [6, 50, 500, 412]

    with qtbot.waitSignal(mmc.events.roiSet):
        crop.click()

    assert cam.value()["Camera2"].roi == ROI(x=6, y=50, w=412, h=412, centered=False)
    assert cam.value()["Camera2"].crop_mode == CUSTOM_ROI
    assert mmc.getROI("Camera2") == [6, 50, 412, 412]
    assert not cam.lbl_info.styleSheet()

    assert cam.value()["Camera2"] == CameraInfo(
        pixel_width=512,
        pixel_height=512,
        crop_mode=CUSTOM_ROI,
        roi=ROI(x=6, y=50, w=412, h=412, centered=False),
    )


def test_core_setROI(qtbot: QtBot, multi_cam_cfg: Path):
    cam = CameraRoiWidget()
    qtbot.addWidget(cam)
    mmc = cam._mmc
    mmc.loadSystemConfiguration(multi_cam_cfg)

    assert cam.camera == "Camera"

    _, roi_combo, x, y, w, h, cbox, _, crop = _get_wdgs(cam)

    # setROI on the selected camera in the combo that also is the core camera
    # non-centered
    with qtbot.waitSignal(mmc.events.roiSet):
        mmc.setROI(10, 10, 100, 100)
    assert cam.value()["Camera"].roi == ROI(x=10, y=10, w=100, h=100, centered=False)
    assert cam.value()["Camera"].crop_mode == CUSTOM_ROI
    assert mmc.getROI("Camera") == [10, 10, 100, 100]
    assert x.value() == 10
    assert y.value() == 10
    assert w.value() == 100
    assert h.value() == 100
    assert roi_combo.currentText() == CUSTOM_ROI
    assert not cbox.isChecked()
    assert crop.isEnabled()
    assert not cam.lbl_info.styleSheet()

    # centered
    with qtbot.waitSignal(mmc.events.roiSet):
        mmc.setROI(156, 156, 200, 200)
    assert cam.value()["Camera"].roi == ROI(x=156, y=156, w=200, h=200, centered=True)
    assert cbox.isChecked()

    # setROI on a camera NON-SELECTED in the combo and that is not the core camera
    camera_info = cam.value()["Camera"]
    with qtbot.waitSignal(mmc.events.roiSet):
        mmc.setROI("Camera1", 20, 20, 100, 100)

    # "Camera" info should not change as well as the gui
    assert cam.value()["Camera"] == camera_info
    assert cam.value()["Camera1"].roi == ROI(x=20, y=20, w=100, h=100, centered=False)
    assert cam.value()["Camera1"].crop_mode == CUSTOM_ROI
    # the gui should not change
    assert x.value() == 156
    assert y.value() == 156
    assert w.value() == 200
    assert h.value() == 200


def test_roi_changed_signal(qtbot: QtBot):
    cam = CameraRoiWidget()
    qtbot.addWidget(cam)

    mock = Mock()
    cam.roiChanged.connect(mock)

    cam.camera_roi_combo.setCurrentText("256 x 256")
    mock.assert_has_calls([call(128, 128, 256, 256, "256 x 256")])

    cam.camera_roi_combo.setCurrentText(FULL)
    mock.assert_has_calls([call(0, 0, 512, 512, FULL)])

    cam.camera_roi_combo.setCurrentText(CUSTOM_ROI)
    mock.assert_has_calls([call(0, 0, 512, 512, CUSTOM_ROI)])

    cam.roi_width.setValue(100)
    assert cam.center_checkbox.isChecked()
    mock.assert_has_calls([call(206, 0, 100, 512, CUSTOM_ROI)])

    cam.roi_height.setValue(200)
    mock.assert_has_calls([call(206, 156, 100, 200, CUSTOM_ROI)])

    cam.center_checkbox.setChecked(False)
    cam.start_x.setValue(10)
    mock.assert_has_calls([call(10, 156, 100, 200, CUSTOM_ROI)])

    cam.start_y.setValue(20)
    mock.assert_has_calls([call(10, 20, 100, 200, CUSTOM_ROI)])
