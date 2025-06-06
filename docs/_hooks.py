from __future__ import annotations

import atexit
import os
import subprocess
from pathlib import Path
from tempfile import mkstemp
from typing import TYPE_CHECKING

from mkdocs.structure.files import File, Files, InclusionLevel
from qtpy.QtWidgets import QWidget

import pymmcore_widgets

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig

EXAMPLES = Path(__file__).parent.parent / "examples"
WIDGET_LIST: list[str] = []
for name in dir(pymmcore_widgets):
    cls = getattr(pymmcore_widgets, name)
    if isinstance(cls, type) and issubclass(cls, QWidget):
        WIDGET_LIST.append(name)


def _camel_to_snake(name: str) -> str:
    import re

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


TEMPLATE = """
# {widget}

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

from rich import print


def on_files(files: Files, /, *, config: MkDocsConfig) -> None:
    for widget in WIDGET_LIST:
        print("Generating snapshot for....", widget)
        snake = _camel_to_snake(widget)
        path = EXAMPLES / f"{_camel_to_snake(widget)}.py"
        if not path.exists():
            print(f"Could not find example: {path}, {widget}")
            continue
        img_uri = f"images/{snake}.png"
        abs_png = snapshot(str(path))
        png = File.generated(
            config=config,
            src_uri=img_uri,
            abs_src_path=abs_png,
            inclusion=InclusionLevel.NOT_IN_NAV,
        )
        files.append(png)
        print("Generated snapshot for", widget, "at", img_uri, png)
        file = File.generated(
            config,
            src_uri=os.path.join("widgets", f"{widget}.md"),
            content=TEMPLATE.format(widget=widget, snake=snake, img=img_uri),
        )
        if file.src_uri in files.src_uris:
            files.remove(file)
        files.append(file)


SNAP = """
app = QApplication.instance()
app.processEvents()
print(app.topLevelWidgets())
widget = next(
    w for w in app.topLevelWidgets()
    if any(n in w.__class__.__module__ for n in ["pymmcore", "__main__"])
)
widget.setMinimumWidth(300)
app.processEvents()
widget.grab().save({})
app.processEvents()
"""


def snapshot(filename: str) -> str:
    """Run filename in a subprocess and snapshot top level widget.

    replace calls to `app.exec()` with a function that calls processEvents() and then
    grabs the top level widget, saving it to filename.
    """
    fpath = Path(filename)
    dest = mkstemp(prefix=fpath.stem, suffix=".png")[1]
    atexit.register(os.remove, dest)
    append = SNAP.format(repr(dest))
    src = fpath.read_text().strip()
    src = src.replace("app.exec_()", append).replace("app.exec()", append)
    subprocess.run(["python", "-c", src], check=True)
    return dest
