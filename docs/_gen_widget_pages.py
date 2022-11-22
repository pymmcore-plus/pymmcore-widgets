from pathlib import Path

WIDGETS = Path(__file__).parent / "widgets"
EXAMPLES = Path(__file__).parent.parent / "examples"


def _widget_list() -> list[str]:
    from qtpy.QtWidgets import QWidget

    import pymmcore_widgets

    widgets = []
    for name in dir(pymmcore_widgets):
        if name.startswith("_"):
            continue
        obj = getattr(pymmcore_widgets, name)
        if isinstance(obj, type) and issubclass(obj, QWidget):
            widgets.append(name)
    return sorted(widgets)


def _camel_to_snake(name: str) -> str:
    import re

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _example_screenshot(name):
    path = EXAMPLES / f"{name}.py"
    if not path.exists():
        return ""

    from qtpy.QtWidgets import QApplication

    src = path.read_text().strip()
    src = src.replace("QApplication([])", "QApplication.instance() or QApplication([])")
    src = src.replace("self.mmc.loadSystemConfiguration()", "")
    src = src.replace("mmc.loadSystemConfiguration()", "")
    src = src.replace("app.exec_()", "")
    try:
        exec(src, globals(), globals())
    except Exception:
        breakpoint()

    app = QApplication.instance() or QApplication([])
    app.topLevelWidgets()
    for widget in app.topLevelWidgets():
        widget.show()
        widget.grab().save(f"screenshot_{name}.png")
        widget.close()
        widget.deleteLater()
    app.processEvents()
    app.processEvents()
    # breakpoint()
    # w = _w(app)
    # w.activateWindow()
    # if width:
    # w.setFixedWidth(width)
    # w.grab().save(dest)


def generate_widget_pages() -> None:
    """Auto-Generate pages in the widgets folder."""
    from textwrap import dedent

    import mkdocs_gen_files

    for widget in _widget_list():
        if (WIDGETS / f"{widget}.md").exists():
            # skip existing files
            continue

        filename = f"widgets/{widget}.md"
        snake = _camel_to_snake(widget)

        _ = _example_screenshot(snake)

        with mkdocs_gen_files.open(filename, "w") as f:
            md = f"""
            ::: pymmcore_widgets.{widget}

            ## Example

            ```python linenums="1" title="{snake}.py"
            --8<-- "examples/{snake}.py"
            ```
            """
            f.write(dedent(md))

        mkdocs_gen_files.set_edit_path(filename, Path(__file__).name)


generate_widget_pages()
