# DeviceWidget

::: pymmcore_widgets.DeviceWidget

!!! Note
    Currently, `DeviceWidget` only supports devices of type `StateDevice`. Calling
    `DeviceWidget.for_device("device_label")`, will create the `DeviceWidget` subclass
    [StateDeviceWidget](StateDeviceWidget.md).

## Examples

### Load all devices of type `StateDevice`.

In this example all the devices of type `StateDevice` that are loaded in micromanager
are dysplaied with a `DeviceWidget`.

{{ include_example('device_widget.py') }}

{{ show_image('device_widget.py') }}
