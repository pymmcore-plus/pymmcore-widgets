from pathlib import Path
from typing import cast

import yaml

widget_list_yaml = Path(__file__).parent / "widget_list.yaml"


def on_page_markdown(md: str, **kwargs):
    """Called when the markdown for a page is loaded."""
    with open(widget_list_yaml) as f:
        widget_dict = yaml.safe_load(f)

        for widget in widget_dict:
            widget = cast(str, widget)
            if widget.upper() in md:  # e.g. CONFIGURATION_WIDGETS in index.md
                md = md.replace(
                    "{{ " + f"{widget.upper()}" + " }}",
                    _widget_table(widget_dict[widget]),
                )
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
            table.append(f"| [{name}][pymmcore_widgets.{name}] | {doc} |")

    return "\n".join(table)
