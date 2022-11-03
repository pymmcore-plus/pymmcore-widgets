# StateDeviceWidget

::: pymmcore_widgets._device_widget.StateDeviceWidget

## Examples

In this example all the devices of type `StateDevice` that are loaded in micromanager
are dysplaied with a `StateDeviceWidget`.

{{ include_example('state_device_widget.py') }}

{{ show_image('state_device_widget.py') }}

An identical result can be obtained using the `DeviceWidget.for_device('device_label')`
method (see [DeviceWidget](DeviceWidget.md)).
