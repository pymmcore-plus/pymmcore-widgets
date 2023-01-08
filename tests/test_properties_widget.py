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
