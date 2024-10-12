import faulthandler

import pytest
from pymmcore_plus import CMMCorePlus, PropertyType

from pymmcore_widgets import PropertyWidget

faulthandler.enable()

# not sure how else to parametrize the test without instantiating here at import ...
# NOTE: in the default 'MMConfig_demo.cgf', the device called 'LED'
# is a mock State Device (DStateDevice) device from the 'DemoCamera DHub.
# We are excluding the dev-prop 'LED-Number of positions' because
# it is not an actual property of the device, but it is only used
# in the micromanager "Hardwre Configuration Wizard" to set the number
# of states (by default, 10) that the mock device can have.
CORE = CMMCorePlus()
CORE.loadSystemConfiguration()
dev_props = [
    (dev, prop)
    for dev in CORE.getLoadedDevices()
    for prop in CORE.getDevicePropertyNames(dev)
    if dev != "LED" and prop not in {"Number of positions", "Initialize"}
]


def _assert_equal(a, b):
    try:
        assert float(a) == float(b)
    except ValueError:
        assert str(a) == str(b)


@pytest.mark.parametrize("dev, prop", dev_props)
def test_property_widget(dev, prop, qtbot) -> None:
    wdg = PropertyWidget(dev, prop, mmcore=CORE)
    qtbot.addWidget(wdg)
    if CORE.isPropertyReadOnly(dev, prop) or prop in (
        "SimulateCrash",
        "Trigger",
        "AsyncPropertyLeader",
    ):
        return

    start_val = CORE.getProperty(dev, prop)
    _assert_equal(wdg.value(), start_val)

    # make sure that setting the value via the widget updates core
    if allowed := CORE.getAllowedPropertyValues(dev, prop):
        val = allowed[-1]
    elif CORE.getPropertyType(dev, prop) in (PropertyType.Integer, PropertyType.Float):
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
        val = _vals.get(prop, 1)
    else:
        val = "some string"

    before = wdg.value()
    wdg.setValue(val)

    strict_init = hasattr(CORE, "isFeatureEnabled") and CORE.isFeatureEnabled(
        "StrictInitializationChecks"
    )
    if CORE.isPropertyPreInit(dev, prop) and strict_init:
        # as of pymmcore 10.7.0.71.0, setting pre-init properties
        # after the device has been initialized does nothing.
        _assert_equal(wdg.value(), before)
        return

    _assert_equal(wdg.value(), val)
    _assert_equal(CORE.getProperty(dev, prop), val)

    # make sure that setting value via core updates the widget
    CORE.setProperty(dev, prop, start_val)
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
