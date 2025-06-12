# Widgets List

Below there is a list of all the widgets available in this package **grouped by their functionality**.

## Camera Widgets

The widgets in this section can be used to **control** any `Micro-Manager`
device of type [CameraDevice][pymmcore_plus.DeviceType.CameraDevice]

| Widget | Description |
| ------ | ----------- |
| [CameraRoiWidget](./CameraRoiWidget.md) | A Widget to control the camera device ROI. |
| [DefaultCameraExposureWidget](./DefaultCameraExposureWidget.md) | A Widget to get/set exposure on the default camera. |
| [ExposureWidget](./ExposureWidget.md) | A Widget to get/set exposure on a camera. |

## Configuration Widgets

The widgets in this section can be used to **create, load and modify a
Micro-Manager configuration** file.

| Widget | Description |
| ------ | ----------- |
| [ConfigWizard](./ConfigWizard.md) | Hardware Configuration Wizard for Micro-Manager. |
| [ConfigurationWidget](./ConfigurationWidget.md) | A Widget to select and load a micromanager system configuration. |
| [GroupPresetTableWidget](./GroupPresetTableWidget.md) | A Widget to create, edit, delete and set micromanager group presets. |
| [InstallWidget](./InstallWidget.md) | Widget to manage installation of MicroManager. |
| [ObjectivesPixelConfigurationWidget](./ObjectivesPixelConfigurationWidget.md) | A Widget to define the pixel size configurations using the objective device. |
| [PixelConfigurationWidget](./PixelConfigurationWidget.md) | A Widget to define the pixel size configurations. |
| [PresetsWidget](./PresetsWidget.md) | A Widget to create a QCombobox containing the presets of the specified group. |

## Devices and Properties Widgets

The widgets in this section can be used to **control and intract with the
devices and properties** of a `Micro-Manager` core
([CMMCorePlus][pymmcore_plus.CMMCorePlus]).

| Widget | Description |
| ------ | ----------- |
| [PropertiesWidget](./PropertiesWidget.md) | Convenience container to control a specific set of PropertyWidgets. |
| [PropertyBrowser](./PropertyBrowser.md) | A Widget to browse and change properties of all devices. |
| [PropertyWidget](./PropertyWidget.md) | A widget to display and control a specified mmcore device property. |

## Multi-Dimensional Acquisition Widgets

The widgets in this section can be used to **define (and run) a
multi-dimensional acquisition** based on the [useq-schema MDASequence][useq.MDASequence].

| Widget | Description |
| ------ | ----------- |
| [ChannelTable](./ChannelTable.md) | Table to edit a list of [useq.Channels](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Channel). |
| [GridPlanWidget](./GridPlanWidget.md) | Widget to edit a [`useq-schema` GridPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans). |
| [MDASequenceWidget](./MDASequenceWidget.md) | A widget that provides a GUI to construct and edit a [`useq-schema` MDASequence][useq.MDASequence]. |
| [MDAWidget](./MDAWidget.md) | Main MDA Widget connected to a [`pymmcore_plus.CMMCorePlus`][] instance. |
| [PositionTable](./PositionTable.md) | Table to edit a list of [useq.Position](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Position). |
| [TimePlanWidget](./TimePlanWidget.md) | Table to edit a [useq.TimePlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#time-plans). |
| [ZPlanWidget](./ZPlanWidget.md) | Widget to edit a [useq.ZPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#z-plans). |

## Shutter Widgets

The widgets in this section can be used to **control** any `Micro-Manager`
[ShutterDevice][pymmcore_plus.DeviceType.ShutterDevice].

| Widget | Description |
| ------ | ----------- |
| [ShuttersWidget](./ShuttersWidget.md) | A Widget to control shutters and Micro-Manager autoshutter. |

## Stage Widgets

The widgets in this section can be used to **control** any `Micro-Manager`
[StageDevice][pymmcore_plus.DeviceType.StageDevice].

| Widget | Description |
| ------ | ----------- |
| [StageWidget](./StageWidget.md) | A Widget to control a XY and/or a Z stage. |

## Misc Widgets

The widgets in this section are **miscellaneous** widgets that can be used for different purposes.

| Widget | Description |
| ------ | ----------- |
| [ChannelGroupWidget](./ChannelGroupWidget.md) | A QComboBox to follow and control Micro-Manager ChannelGroup. |
| [ChannelWidget](./ChannelWidget.md) | A QComboBox to select which micromanager channel configuration to use. |
| [CoreLogWidget](./CoreLogWidget.md) | High-performance log console with pause, follow-tail, clear, and initial load. |
| [ImagePreview](./ImagePreview.md) | A Widget that displays the last image snapped by active core. |
| [LiveButton](./LiveButton.md) | A Widget to create a two-state (on-off) live mode QPushButton. |
| [ObjectivesWidget](./ObjectivesWidget.md) | A QComboBox-based Widget to select the microscope objective. |
| [SnapButton](./SnapButton.md) | Create a snap QPushButton. |
