import json
from pathlib import Path
from textwrap import dedent

import mkdocs_gen_files
from pymmcore_plus.core import _mmcore_plus

WIDGET_LIST = Path(__file__).parent / "widget_list.json"
WIDGETS = Path(__file__).parent / "widgets"
EXAMPLES = Path(__file__).parent.parent / "examples"
TEMPLATE = """
<figure markdown>
  ![{widget} widget](../{img}){{ loading=lazy, class="widget-image" }}
  <figcaption>
    This image generated from <a href="#example">example code below</a>.
  </figcaption>
</figure>

::: pymmcore_widgets.{widget}

## Example

```python linenums="1" title="{snake}.py"
--8<-- "examples/{snake}.py"
```
"""


def _camel_to_snake(name: str) -> str:
    import re

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


SEEN: set[int] = set()


def _example_screenshot(cls_name: str, dest: str) -> None:
    path = EXAMPLES / f"{_camel_to_snake(cls_name)}.py"
    if not path.exists():
        raise ValueError(f"Could not find example: {path}")

    from qtpy.QtWidgets import QApplication

    src = path.read_text().strip()
    src = src.replace("QApplication([])", "QApplication.instance() or QApplication([])")
    src = src.replace("app.exec_()", "")
    src = src.replace("app.exec()", "")
    gl = {**globals().copy(), "__name__": "__main__"}
    exec(src, gl, gl)

    app = QApplication.instance() or QApplication([])
    new = [w for w in app.topLevelWidgets() if id(w) not in SEEN]
    # remove all classes that are Qframe or QMenu
    new = [w for w in new if w.__class__.__name__ not in ["QFrame", "QMenu"]]
    SEEN.update(id(w) for w in new)
    if new:
        widget = next((w for w in new if w.__class__.__name__ == cls_name), new[0])
        widget.setMinimumWidth(300)  # turns out this is very important for grab
        widget.grab().save(dest)

    # clean up core instance and application
    del _mmcore_plus._instance
    _mmcore_plus._instance = None
    for w in app.topLevelWidgets():
        w.deleteLater()


def _generate_widget_page(widget: str) -> None:
    """Auto-Generate pages in the widgets folder."""
    filename = f"widgets/{widget}.md"
    snake = _camel_to_snake(widget)
    print("Generating", filename)
    img = f"images/{snake}.png"
    with mkdocs_gen_files.open(img, "wb") as f:
        _example_screenshot(widget, f.name)

    with mkdocs_gen_files.open(filename, "w") as f:
        f.write(dedent(TEMPLATE.format(widget=widget, snake=snake, img=img)))

    mkdocs_gen_files.set_edit_path(filename, Path(__file__).name)


def _generate_widget_pages() -> None:
    # it would be nice to do this in parallel,
    # but mkdocs_gen_files doesn't work well with multiprocessing
    with open(WIDGET_LIST) as f:
        widget_dict = json.load(f)

        for _, widgets in widget_dict.items():
            for widget in widgets:
                #  skip classes that have manual examples
                if not (WIDGETS / f"{widget}.md").exists():
                    _generate_widget_page(widget)


_generate_widget_pages()
