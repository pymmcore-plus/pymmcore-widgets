from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

import pymmcore_widgets as pmmw
import pymmcore_widgets.mda as mdapmmw
import pymmcore_widgets.old_mda as oldmdapmmw
import pymmcore_widgets.useq_widgets as useqpmmw

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtWidgets import QWidget

ALL_WIDGETS: dict[type[QWidget], dict[str, Any]] = {
    pmmw.CameraRoiWidget: {},
    pmmw.ChannelGroupWidget: {},
    pmmw.ChannelWidget: {},
    pmmw.ConfigurationWidget: {},
    pmmw.DefaultCameraExposureWidget: {},
    pmmw.DeviceWidget: {"device_label": "Camera"},
    pmmw.ExposureWidget: {},
    pmmw.GroupPresetTableWidget: {},
    pmmw.ImagePreview: {},
    pmmw.LiveButton: {},
    pmmw.ObjectivesWidget: {},
    pmmw.PixelSizeWidget: {},
    pmmw.PresetsWidget: {"group": "Camera"},
    pmmw.PropertiesWidget: {},
    pmmw.PropertyBrowser: {},
    pmmw.PropertyWidget: {"device_label": "Camera", "prop_name": "Binning"},
    pmmw.ShuttersWidget: {"shutter_device": "Shutter"},
    pmmw.SnapButton: {},
    pmmw.StageWidget: {"device": "XY"},
    pmmw.StateDeviceWidget: {"device_label": "Objective"},
    useqpmmw.ChannelTable: {},
    useqpmmw.TimePlanWidget: {},
    useqpmmw.PositionTable: {},
    useqpmmw.ZPlanWidget: {},
    useqpmmw.GridPlanWidget: {},
    mdapmmw.CoreConnectedGridPlanWidget: {},
    mdapmmw.CoreConnectedZPlanWidget: {},
    # not sure why, but the CoreConnectedPositionTable triggers the _run_after_each_test
    # so exclude it for now
    # mdapmmw.CoreConnectedPositionTable: {},
    oldmdapmmw.OldChannelTable: {},
    oldmdapmmw.OldTimePlanWidget: {},
    oldmdapmmw.OldPositionTable: {},
    oldmdapmmw.OldZStackWidget: {},
    oldmdapmmw.OldGridWidget: {},
}


def _full_state(core: CMMCorePlus) -> dict:
    state: dict = dict(core.state())
    state.pop("Datetime", None)
    for prop in core.iterProperties():
        state[(prop.device, prop.name)] = prop.value
    return state


@pytest.mark.parametrize("widget", ALL_WIDGETS, ids=lambda x: x.__name__)
def test_core_state_unchanged(
    global_mmcore: CMMCorePlus, widget: type[QWidget], qtbot
) -> None:
    before = _full_state(global_mmcore)
    kwargs = {**ALL_WIDGETS[widget]}
    w = widget(**kwargs)
    qtbot.addWidget(w)
    after = _full_state(global_mmcore)
    assert before == after


def test_all_widgets_represented() -> None:
    if missing_widgets := {cls.__name__ for cls in ALL_WIDGETS}.difference(
        (*pmmw.__all__, *useqpmmw.__all__, *mdapmmw.__all__, *oldmdapmmw.__all__)
    ):
        raise AssertionError(
            f"Some widgets are missing from the ALL_WIDGETS test dict: "
            f"{missing_widgets}"
        )
