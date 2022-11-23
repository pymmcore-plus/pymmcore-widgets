from pathlib import Path


def _camel_to_snake(name: str) -> str:
    import re

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


WIDGETS = Path(__file__).parent / "widgets"
EXAMPLES = Path(__file__).parent / "examples"
SEEN: set[int] = set()


def _example_screenshot(cls_name: str) -> str:
    path = EXAMPLES / f"{_camel_to_snake(cls_name)}.py"
    if not path.exists():
        return ""

    from qtpy.QtWidgets import QApplication

    src = path.read_text().strip()
    src = src.replace("QApplication([])", "QApplication.instance() or QApplication([])")
    src = src.replace("app.exec_()", "")
    gl = {**globals().copy(), "__name__": "__main__"}
    exec(src, gl, gl)

    name = f"{cls_name}.png"
    app = QApplication.instance() or QApplication([])
    new = [w for w in app.topLevelWidgets() if id(w) not in SEEN]
    SEEN.update(id(w) for w in new)

    widget = next((w for w in new if w.__class__.__name__ == cls_name), None)
    if widget is None:
        widget = next((w for w in new if w.__class__.__name__ != "QFrame"), new[0])
    widget.setMinimumWidth(300)  # turns out this is very important for grab
    widget.grab().save(f"{name}")

    for w in app.topLevelWidgets():
        w.deleteLater()
    return name


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


if __name__ == "__main__":
    from concurrent.futures import ProcessPoolExecutor

    widgets = _widget_list()
    with ProcessPoolExecutor() as pool:
        list(pool.map(_example_screenshot, widgets))
