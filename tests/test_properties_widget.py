from pymmcore_plus import PropertyType

from pymmcore_widgets import PropertiesWidget


def test_properties_widget(qtbot):
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
    assert widget.layout().count() > 0
