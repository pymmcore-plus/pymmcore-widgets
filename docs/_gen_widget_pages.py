import warnings
from pathlib import Path
from textwrap import dedent

import mkdocs_gen_files

WIDGETS = Path(__file__).parent / "widgets"
EXAMPLES = Path(__file__).parent.parent / "examples"
TEMPLATE = """
<figure markdown>
  ![{widget} widget](../{img}){{ loading=lazy, class="widget-image" }}
  <figcaption>
    This image generated from <a href="#example">example code below</a>.
  </figcaption>
</figure>



::: {sub_module}.{widget}

## Example

```python linenums="1" title="{snake}.py"
--8<-- "examples/{snake}.py"
```
"""


def _get_widget_list(module: str) -> list[tuple[str, str]]:
    from qtpy.QtWidgets import QWidget

    widgets = []
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, type) and issubclass(obj, QWidget):
            widgets.append((name, module.__name__))
    return widgets


def _widget_list() -> list[tuple[str, str]]:
    import pymmcore_widgets
    import pymmcore_widgets.mda
    import pymmcore_widgets.useq_widgets

    widgets = _get_widget_list(pymmcore_widgets)
    widgets.extend(_get_widget_list(pymmcore_widgets.useq_widgets))
    widgets.extend(_get_widget_list(pymmcore_widgets.mda))

    return sorted(widgets, key=lambda x: x[0])


def _camel_to_snake(name: str) -> str:
    import re

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


SEEN: set[int] = set()


def _example_screenshot(cls_name: str, dest: str) -> None:
    path = EXAMPLES / f"{_camel_to_snake(cls_name)}.py"
    if not path.exists():
        # raise ValueError(f"Could not find example: {path}")
        warnings.warn(f"Could not find example: {path}", stacklevel=2)
        return

    from qtpy.QtWidgets import QApplication

    src = path.read_text().strip()
    src = src.replace("QApplication([])", "QApplication.instance() or QApplication([])")
    src = src.replace("app.exec_()", "")
    src = src.replace("app.exec()", "")
    gl = {**globals().copy(), "__name__": "__main__"}
    exec(src, gl, gl)

    app = QApplication.instance() or QApplication([])
    new = [w for w in app.topLevelWidgets() if id(w) not in SEEN]
    SEEN.update(id(w) for w in new)
    if not new:
        return
    widget = next((w for w in new if w.__class__.__name__ == cls_name), None) or next(
        (w for w in new if w.__class__.__name__ != "QFrame"), new[0]
    )
    widget.setMinimumWidth(300)  # turns out this is very important for grab
    widget.grab().save(dest)

    widget.grab().save(f"/Users/fdrgsp/Desktop/test/{_camel_to_snake(cls_name)}.png")

    for w in app.topLevelWidgets():
        w.deleteLater()


def _generate_widget_page(widget: list[tuple[str, str]]) -> None:
    """Auto-Generate pages in the widgets folder."""
    widget, sub_module = widget
    filename = f"widgets/{widget}.md"
    snake = _camel_to_snake(widget)
    print("Generating", filename)
    img = f"images/{snake}.png"
    with mkdocs_gen_files.open(img, "wb") as f:
        _example_screenshot(widget, f.name)
    with mkdocs_gen_files.open(filename, "w") as f:
        f.write(
            dedent(
                TEMPLATE.format(
                    widget=widget, sub_module=sub_module, snake=snake, img=img
                )
            )
        )

    mkdocs_gen_files.set_edit_path(filename, Path(__file__).name)


def _generate_widget_pages() -> None:
    # skip classes that have manual examples
    widgets = [w for w in _widget_list() if not (WIDGETS / f"{w}.md").exists()]

    # it would be nice to do this in parallel,
    # but mkdocs_gen_files doesn't work well with multiprocessing
    list(map(_generate_widget_page, widgets))


_generate_widget_pages()
