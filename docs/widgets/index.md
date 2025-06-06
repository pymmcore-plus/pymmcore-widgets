# Widgets List

Below there is a list of all the widgets available in this package **grouped by their functionality**.

## Camera Widgets

The widgets in this section can be used to **control** any `Micro-Manager`
device of type [CameraDevice][pymmcore_plus.DeviceType.CameraDevice]

| Widget | Description |
| ------ | ----------- |
| [CameraRoiWidget](/widgets/CameraRoiWidget) | A Widget to control the camera device ROI. |
| [DefaultCameraExposureWidget](/widgets/DefaultCameraExposureWidget) | A Widget to get/set exposure on the default camera. |
| [ExposureWidget](/widgets/ExposureWidget) | A Widget to get/set exposure on a camera. |

## Configuration Widgets

The widgets in this section can be used to **create, load and modify a
Micro-Manager configuration** file.

| Widget | Description |
| ------ | ----------- |
| [ConfigWizard](/widgets/ConfigWizard) | Hardware Configuration Wizard for Micro-Manager. |
| [ConfigurationWidget](/widgets/ConfigurationWidget) | A Widget to select and load a micromanager system configuration. |
| [GroupPresetTableWidget](/widgets/GroupPresetTableWidget) | A Widget to create, edit, delete and set micromanager group presets. |
| [InstallWidget](/widgets/InstallWidget) | Widget to manage installation of MicroManager. |
| [ObjectivesPixelConfigurationWidget](/widgets/ObjectivesPixelConfigurationWidget) | A Widget to define the pixel size configurations using the objective device. |
| [PixelConfigurationWidget](/widgets/PixelConfigurationWidget) | A Widget to define the pixel size configurations. |
| [PresetsWidget](/widgets/PresetsWidget) | A Widget to create a QCombobox containing the presets of the specified group. |

## Devices and Properties Widgets

The widgets in this section can be used to **control and intract with the
devices and properties** of a `Micro-Manager` core
([CMMCorePlus][pymmcore_plus.CMMCorePlus]).

| Widget | Description |
| ------ | ----------- |
| [PropertiesWidget](/widgets/PropertiesWidget) | Convenience container to control a specific set of PropertyWidgets. |
| [PropertyBrowser](/widgets/PropertyBrowser) | A Widget to browse and change properties of all devices. |
| [PropertyWidget](/widgets/PropertyWidget) | A widget to display and control a specified mmcore device property. |

## Multi-Dimensional Acquisition Widgets

The widgets in this section can be used to **define (and run) a
multi-dimensional acquisition** based on the [useq-schema MDASequence][useqASequence].

| Widget | Description |
| ------ | ----------- |
| [ChannelTable](/widgets/ChannelTable) | Table to edit a list of [useq.Channels](/widgets/https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Channel). |
| [GridPlanWidget](/widgets/GridPlanWidget) | Widget to edit a [`useq-schema` GridPlan](/widgets/https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans). |
| [MDASequenceWidget](/widgets/MDASequenceWidget) | A widget that provides a GUI to construct and edit a [`useqASequence`][]. |
| [MDAWidget](/widgets/MDAWidget) | Main MDA Widget connected to a [`pymmcore_plus.CMMCorePlus`][] instance. |
| [PositionTable](/widgets/PositionTable) | Table to edit a list of [useq.Position](/widgets/https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Position). |
| [TimePlanWidget](/widgets/TimePlanWidget) | Table to edit a [useq.TimePlan](/widgets/https://pymmcore-plus.github.io/useq-schema/schema/axes/#time-plans). |
| [ZPlanWidget](/widgets/ZPlanWidget) | Widget to edit a [useq.ZPlan](/widgets/https://pymmcore-plus.github.io/useq-schema/schema/axes/#z-plans). |

## Shutter Widgets

The widgets in this section can be used to **control** any `Micro-Manager`
[ShutterDevice][pymmcore_plus.DeviceType.ShutterDevice].

| Widget | Description |
| ------ | ----------- |
| [ShuttersWidget](/widgets/ShuttersWidget) | A Widget to control shutters and Micro-Manager autoshutter. |

## Stage Widgets

The widgets in this section can be used to **control** any `Micro-Manager`
[StageDevice][pymmcore_plus.DeviceType.StageDevice].

| Widget | Description |
| ------ | ----------- |
| [StageWidget](/widgets/StageWidget) | A Widget to control a XY and/or a Z stage. |

## Misc Widgets

The widgets in this section are **miscellaneous** widgets that can be used for different purposes.

| Widget | Description |
| ------ | ----------- |
| [ChannelGroupWidget](/widgets/ChannelGroupWidget) | A QComboBox to follow and control Micro-Manager ChannelGroup. |
| [ChannelWidget](/widgets/ChannelWidget) | A QComboBox to select which micromanager channel configuration to use. |
| [CoreLogWidget](/widgets/CoreLogWidget) | High-performance log console with pause, follow-tail, clear, and initial load. |
| [ImagePreview](/widgets/ImagePreview) | A Widget that displays the last image snapped by active core. |
| [LiveButton](/widgets/LiveButton) | A Widget to create a two-state (on-off) live mode QPushButton. |
| [ObjectivesWidget](/widgets/ObjectivesWidget) | A QComboBox-based Widget to select the microscope objective. |
| [SnapButton](/widgets/SnapButton) | Create a snap QPushButton. |
