import faulthandler

import pytest
from pymmcore_plus import CMMCorePlus, PropertyType

from pymmcore_widgets import PropertyWidget

faulthandler.enable()


def _assert_equal(a, b):
    try:
        assert float(a) == float(b)
    except ValueError:
        assert str(a) == str(b)


def test_property_widget(global_mmcore: CMMCorePlus, qtbot) -> None:
    # these are just numbers that work for the test config devices
    _vals = {
        "TestProperty": 1,
        "Photon Flux": 50,
        "TestProperty1": 0.01,
        "TestProperty3": 0.002,
        "OnCameraCCDXSize": 20,
        "OnCameraCCDYSize": 20,
        "FractionOfPixelsToDropOrSaturate": 0.05,
    }
    core = global_mmcore
    for dev in core.getLoadedDevices():
        if dev == "LED":
            continue
        for prop in core.getDevicePropertyNames(dev):
            if prop in {
                "Number of positions",
                "Initialize",
                "SimulateCrash",
                "Trigger",
            }:
                continue

            wdg = PropertyWidget(dev, prop, mmcore=core)
            qtbot.addWidget(wdg)
            if wdg.isReadOnly():
                continue

            start_val = core.getProperty(dev, prop)
            _assert_equal(wdg.value(), start_val)
            assert wdg.deviceType() == core.getDeviceType(dev)

            # make sure that setting the value via the widget updates core
            if allowed := wdg.allowedValues():
                val = allowed[-1]
            elif wdg.propertyType() in {PropertyType.Integer, PropertyType.Float}:
                val = _vals.get(prop, 1)
            else:
                val = "some string"

            before = wdg.value()
            wdg.setValue(val)

            strict_init = core.isFeatureEnabled("StrictInitializationChecks")
            if wdg.isPreInit() and strict_init:
                # as of pymmcore 10.7.0.71.0, setting pre-init properties
                # after the device has been initialized does nothing.
                _assert_equal(wdg.value(), before)
                continue

            _assert_equal(wdg.value(), val)
            _assert_equal(core.getProperty(dev, prop), val)

            # make sure that setting value via core updates the widget
            core.setProperty(dev, prop, start_val)
            _assert_equal(wdg.value(), start_val)


def test_prop_widget_signals(global_mmcore: CMMCorePlus, qtbot):
    wdg = PropertyWidget("Camera", "Binning", connect_core=False)
    qtbot.addWidget(wdg)
    assert wdg.value() == "1"
    with qtbot.waitSignal(wdg.valueChanged, timeout=1000):
        wdg._value_widget.setValue(2)
    assert wdg.value() == "2"


def test_reset(global_mmcore: CMMCorePlus, qtbot) -> None:
    wdg = PropertyWidget("Camera", "Binning", mmcore=global_mmcore)
    qtbot.addWidget(wdg)
    global_mmcore.loadSystemConfiguration()
    assert wdg.value()
    # just for coverage
    wdg.refresh()
    assert wdg.inner_widget


def test_bad_val(global_mmcore: CMMCorePlus, qtbot) -> None:
    with pytest.raises(ValueError, match="Device not loaded"):
        PropertyWidget("NotADev", "Binning", mmcore=global_mmcore)
    with pytest.raises(ValueError, match="has no property"):
        PropertyWidget("Camera", "NotAProp", mmcore=global_mmcore)
