from pymmcore_plus import PropertyType
from qtpy.QtWidgets import QLabel

from pymmcore_widgets import PropertiesWidget, PropertyWidget


def test_properties_widget(qtbot, global_mmcore):
    widget = PropertiesWidget(
        property_type={PropertyType.Integer, PropertyType.Float},
        property_name_pattern="(test|camera)s?",
        device_type=None,
        device_label=None,
        has_limits=True,
        is_read_only=False,
        is_sequenceable=False,
    )
    qtbot.addWidget(widget)
    assert widget.layout().count() == 10

    for i in range(widget.layout().count()):
        wdg = widget.layout().itemAt(i).widget()
        if i % 2 == 0:
            assert isinstance(wdg, QLabel)
            assert "Camera::TestProperty" in wdg.text()
        else:
            assert isinstance(wdg, PropertyWidget)
            assert wdg.value() == 0.0
            if i == 5:
                continue
            wdg.setValue(0.1)
            assert wdg.value() == 0.1


def test_property_widget_cross_thread_update(qtbot, global_mmcore):
    """A core event handled on a worker thread must not write back to the core."""
    import threading

    dev, prop = "Camera", "Exposure"  # float with limits: slider + spinbox
    global_mmcore.setProperty(dev, prop, "10")
    wdg = PropertyWidget(dev, prop, mmcore=global_mmcore)
    qtbot.addWidget(wdg)
    assert wdg.value() == 10.0

    writes = []
    orig_set = global_mmcore.setProperty

    def spy(*args, **kwargs):
        writes.append(args)
        return orig_set(*args, **kwargs)

    global_mmcore.setProperty = spy
    try:

        def from_thread() -> None:
            for v in ("20", "30", "40"):
                wdg._on_core_changed(dev, prop, v)

        t = threading.Thread(target=from_thread)
        t.start()
        t.join()
        qtbot.waitUntil(lambda: wdg.value() == 40.0)
        qtbot.wait(100)
    finally:
        global_mmcore.setProperty = orig_set

    assert writes == []
