from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

import pymmcore_widgets as pmmw

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtWidgets import QWidget

ALL_WIDGETS: dict[type[QWidget], dict[str, Any]] = {
    pmmw.PixelConfigurationWidget: {},
    pmmw.CameraRoiWidget: {},
    pmmw.ChannelGroupWidget: {},
    pmmw.ChannelTable: {},
    pmmw.ChannelWidget: {},
    pmmw.ConfigurationWidget: {},
    pmmw.DefaultCameraExposureWidget: {},
    pmmw.ExposureWidget: {},
    pmmw.GridPlanWidget: {},
    pmmw.GroupPresetTableWidget: {},
    pmmw.ImagePreview: {},
    pmmw.LiveButton: {},
    pmmw.MDASequenceWidget: {},
    pmmw.MDAWidget: {},
    pmmw.ObjectivesWidget: {},
    pmmw.ObjectivesPixelConfigurationWidget: {},
    pmmw.PresetsWidget: {"group": "Camera"},
    pmmw.PropertiesWidget: {},
    pmmw.PropertyBrowser: {},
    pmmw.PropertyWidget: {"device_label": "Camera", "prop_name": "Binning"},
    pmmw.ShuttersWidget: {"shutter_device": "Shutter"},
    pmmw.SnapButton: {},
    pmmw.StageWidget: {"device": "XY"},
    pmmw.TimePlanWidget: {},
    pmmw.ZPlanWidget: {},
    pmmw.PositionTable: {},
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
    missing_widgets = {cls.__name__ for cls in ALL_WIDGETS}.difference(pmmw.__all__)
    if missing_widgets:
        raise AssertionError(
            f"Some widgets are missing from the ALL_WIDGETS test dict: "
            f"{missing_widgets}"
        )
