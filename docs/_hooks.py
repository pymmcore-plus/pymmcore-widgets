EXCLUDE = ["DataTable", "DataTableWidget"]


def on_page_markdown(md, **kwargs):
    """Called when the markdown for a page is loaded."""
    if "{{ WIDGET_TABLE }}" in md:
        md = md.replace("{{ WIDGET_TABLE }}", _widget_table())
    return md


def _widget_table():
    import pymmcore_widgets
    import pymmcore_widgets.mda
    import pymmcore_widgets.useq_widgets

    table = _get_widget_table_list(pymmcore_widgets.useq_widgets)
    table += _get_widget_table_list(pymmcore_widgets.mda)
    table += _get_widget_table_list(pymmcore_widgets)

    return table


def _get_widget_table_list(module: str) -> list[str]:
    from qtpy.QtWidgets import QWidget

    table = ["| Widget | Description |", "| ------ | ----------- |"]
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, type) and issubclass(obj, QWidget) and name not in EXCLUDE:
            doc = (obj.__doc__ or "").strip().splitlines()[0]
            table.append(f"| [{name}][{module.__name__}.{name}] | {doc} |")
    return "\n".join(table)
