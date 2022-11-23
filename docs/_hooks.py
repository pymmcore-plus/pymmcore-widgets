def on_page_markdown(md, **kwargs):
    """Called when the markdown for a page is loaded."""
    if "{{ WIDGET_TABLE }}" in md:
        md = md.replace("{{ WIDGET_TABLE }}", _widget_table())
    return md


def _widget_table():
    from qtpy.QtWidgets import QWidget

    import pymmcore_widgets

    table = ["| Widget | Description |", "| ------ | ----------- |"]
    for name in dir(pymmcore_widgets):
        if name.startswith("_"):
            continue
        obj = getattr(pymmcore_widgets, name)
        if isinstance(obj, type) and issubclass(obj, QWidget):
            doc = (obj.__doc__ or "").strip().splitlines()[0]
            table.append(f"| [{name}][pymmcore_widgets.{name}] | {doc} |")
    return "\n".join(table)
