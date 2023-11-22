config_wdgs = [
    "GroupPresetTableWidget",
    "InstallWidget",
    "PixelSizeWidget",
    "ConfigurationWidget",
    "PresetsWidget",
    "ConfigWizard",
]
dev_prop_wdgs = ["PropertyBrowser", "PropertyWidget", "PropertiesWidget"]
mda_wdgs = [
    "MDAWidget",
    "ChannelTable",
    "PositionTable",
    "TimePlanWidget",
    "ZPlanWidget",
    "GridPlanWidget",
    "MDASequenceWidget",
]
misc = [
    "ObjectivesWidget",
    "ShuttersWidget",
    "ChannelGroupWidget",
    "ChannelWidget",
    "ImagePreview",
    "SnapButton",
    "LiveButton",
    "CameraRoiWidget",
    "DefaultCameraExposureWidget",
    "ExposureWidget",
    "StageWidget",
]


def on_page_markdown(md, **kwargs):
    """Called when the markdown for a page is loaded."""
    if "{{ CFG_WIDGET_TABLE }}" in md:
        md = md.replace("{{ CFG_WIDGET_TABLE }}", _widget_table(config_wdgs))
    if "{{ DEV_PROP_WIDGET_TABLE }}" in md:
        md = md.replace("{{ DEV_PROP_WIDGET_TABLE }}", _widget_table(dev_prop_wdgs))
    if "{{ MDA_WIDGET_TABLE }}" in md:
        md = md.replace("{{ MDA_WIDGET_TABLE }}", _widget_table(mda_wdgs))
    if "{{ MISC_WIDGET_TABLE }}" in md:
        md = md.replace("{{ MISC_WIDGET_TABLE }}", _widget_table(misc))
    return md


def _widget_table(widget_list: list[str]):
    from qtpy.QtWidgets import QWidget

    import pymmcore_widgets

    table = ["| Widget | Description |", "| ------ | ----------- |"]
    for name in dir(pymmcore_widgets):
        if name.startswith("_") or name not in widget_list:
            continue
        obj = getattr(pymmcore_widgets, name)
        if isinstance(obj, type) and issubclass(obj, QWidget):
            doc = (obj.__doc__ or "").strip().splitlines()[0]
            # table.append(f"| [{name}][pymmcore_widgets.{name}] | {doc} |")
            table.append(f"| {name} | {doc} |")

    return "\n".join(table)


# def _widget_table():
#     from qtpy.QtWidgets import QWidget

#     import pymmcore_widgets

#     table = ["| Widget | Description |", "| ------ | ----------- |"]
#     for name in dir(pymmcore_widgets):
#         if name.startswith("_"):
#             continue
#         obj = getattr(pymmcore_widgets, name)
#         if isinstance(obj, type) and issubclass(obj, QWidget):
#             doc = (obj.__doc__ or "").strip().splitlines()[0]
#             # table.append(f"| [{name}][pymmcore_widgets.{name}] | {doc} |")
#             table.append(f"| {name} | {doc} |")
#     return "\n".join(table)
