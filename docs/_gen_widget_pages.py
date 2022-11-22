from pathlib import Path

import mkdocs_gen_files

WIDGETS = Path(__file__).parent / "widgets"
EXAMPLES = Path(__file__).parent.parent / "examples"
TEMPLATE = """
::: pymmcore_widgets.{widget}

## Example

```python linenums="1" title="{snake}.py"
--8<-- "examples/{snake}.py"
```

![Example](../{img})
"""


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


GRABBED = set()


def _example_screenshot(cls_name) -> str:
    path = EXAMPLES / f"{_camel_to_snake(cls_name)}.py"
    if not path.exists():
        return ""
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtWidgets import QApplication

    src = path.read_text().strip()
    src = src.replace("QApplication([])", "QApplication.instance() or QApplication([])")
    src = src.replace("self.mmc.loadSystemConfiguration()", "")
    src = src.replace("mmc.loadSystemConfiguration()", "")
    src = src.replace("app.exec_()", "")

    gl = globals().copy()
    gl["__name__"] = "__main__"
    try:
        exec(src, gl, gl)
    except Exception as e:
        print("FAIL", cls_name, e)
        return ""

    name = f"{cls_name}.png"

    app = QApplication.instance() or QApplication([])
    app.topLevelWidgets()

    candidates = [w for w in app.topLevelWidgets() if id(w) not in GRABBED]

    GRABBED.update({id(w) for w in app.topLevelWidgets()})

    if len(candidates) > 1:
        widget = next(w for w in candidates if w.__class__.__name__ == cls_name)
    elif len(candidates) == 1:
        widget = candidates[0]

    widget.show()
    widget.activateWindow()
    QApplication.processEvents()
    QApplication.processEvents()
    # w.setFixedWidth(width)
    with mkdocs_gen_files.open(name, "wb") as f:
        widget.grab().save(f.name)
        print("saved", f.name)

    for w in app.topLevelWidgets():
        w.close()
        w.deleteLater()

    QApplication.processEvents()
    QApplication.processEvents()
    mmc = CMMCorePlus().instance()
    mmc.unloadAllDevices()
    mmc.waitForSystem()

    return name


def generate_widget_pages() -> None:
    """Auto-Generate pages in the widgets folder."""
    from textwrap import dedent

    for widget in _widget_list():
        if (WIDGETS / f"{widget}.md").exists():
            # skip existing files
            continue

        filename = f"widgets/{widget}.md"
        snake = _camel_to_snake(widget)

        img = _example_screenshot(widget)
        if not img:
            print("no image for ", widget)

        with mkdocs_gen_files.open(filename, "w") as f:
            f.write(dedent(TEMPLATE.format(widget=widget, snake=snake, img=img)))

        mkdocs_gen_files.set_edit_path(filename, Path(__file__).name)


generate_widget_pages()
