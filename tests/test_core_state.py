from __future__ import annotations

from typing import Any

import pytest
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QWidget

import pymmcore_widgets as pmmw

ALL_WIDGETS: dict[type[QWidget], dict[str, Any]] = {
    pmmw.CameraRoiWidget: {},
    pmmw.ChannelGroupWidget: {},
    pmmw.ChannelTable: {},
    pmmw.ChannelWidget: {},
    pmmw.ConfigurationWidget: {},
    pmmw.DefaultCameraExposureWidget: {},
    pmmw.DeviceWidget: {"device_label": "Camera"},
    pmmw.ExposureWidget: {},
    pmmw.GridWidget: {},
    pmmw.GroupPresetTableWidget: {},
    pmmw.ImagePreview: {},
    pmmw.LiveButton: {},
    pmmw.MDAWidget: {},
    pmmw.ObjectivesWidget: {},
    pmmw.PixelSizeWidget: {},
    pmmw.PositionTable: {},
    pmmw.PresetsWidget: {"group": "Camera"},
    pmmw.PropertiesWidget: {},
    pmmw.PropertyBrowser: {},
    pmmw.PropertyWidget: {"device_label": "Camera", "prop_name": "Binning"},
    pmmw.ShuttersWidget: {"shutter_device": "Shutter"},
    pmmw.SnapButton: {},
    pmmw.StageWidget: {"device": "XY"},
    pmmw.StateDeviceWidget: {"device_label": "Objective"},
    pmmw.TimePlanWidget: {},
    pmmw.ZStackWidget: {},
}


@pytest.mark.parametrize("widget", ALL_WIDGETS, ids=lambda x: x.__name__)
def test_core_state_unchanged(
    global_mmcore: CMMCorePlus, widget: type[QWidget], qapp: Any
) -> None:
    before = global_mmcore.state()
    kwargs = {**ALL_WIDGETS[widget]}
    widget(**kwargs)
    after = global_mmcore.state()
    before.pop("Datetime", None)
    after.pop("Datetime", None)
    assert before == after


def test_all_widgets_represented() -> None:
    missing_widgets = {cls.__name__ for cls in ALL_WIDGETS}.difference(pmmw.__all__)
    if missing_widgets:
        raise AssertionError(
            f"Some widgets are missing from the ALL_WIDGETS test dict: "
            f"{missing_widgets}"
        )
