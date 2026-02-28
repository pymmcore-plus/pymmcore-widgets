import json
from pathlib import Path
from typing import Any, cast

from qtpy.QtWidgets import QWidget

import pymmcore_widgets

WIDGET_LIST = Path(__file__).parent / "widget_list.json"


def on_page_markdown(md: str, **_: Any) -> str:
    """Called when the markdown for a page is loaded."""
    with open(WIDGET_LIST) as f:
        widget_dict = json.load(f)

        for section, widget_list in widget_dict.items():
            # e.g.  {{ CONFIGURATION_WIDGETS }} in index.md
            section_key = "{{ " + cast("str", section).upper() + " }}"
            if section_key in md:
                md = md.replace(section_key, _widget_table(widget_list))
        return md


def _widget_table(widget_list: list[str]) -> str:
    table = ["| Widget | Description |", "| ------ | ----------- |"]
    for name in dir(pymmcore_widgets):
        if name.startswith("_") or name not in widget_list:
            continue
        obj = getattr(pymmcore_widgets, name)
        if isinstance(obj, type) and issubclass(obj, QWidget):
            doc = (obj.__doc__ or "").strip().splitlines()[0]
            table.append(f"| [{name}]({name}.md) | {doc} |")

    return "\n".join(table)
