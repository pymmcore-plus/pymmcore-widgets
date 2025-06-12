from __future__ import annotations

import atexit
import os
import subprocess
import time
from pathlib import Path
from tempfile import mkstemp
from typing import TYPE_CHECKING

from mkdocs.plugins import get_plugin_logger
from mkdocs.structure.files import File, Files, InclusionLevel
from mkdocs.structure.pages import Page
from qtpy.QtWidgets import QApplication, QWidget
from mkdocs.structure.nav import Navigation, Section

import pymmcore_widgets

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig

logger = get_plugin_logger("pymmcore_widgets")
GEN_SCREENSHOTS = os.getenv("GEN_SCREENSHOTS", "1") in ("1", "true", "yes", "on")
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

WIDGET_FILES: dict[str, File] = {}


def on_files(files: Files, /, *, config: MkDocsConfig) -> None:
    widget_index = next(
        f
        for f in files
        if "widgets/index.md" in f.src_uri and "-widgets/index.md" not in f.src_uri
    )
    root = str(widget_index.src_uri).rsplit("/", 1)[0]
    for widget in WIDGET_LIST:
        snake = _camel_to_snake(widget)
        example = EXAMPLES / f"{_camel_to_snake(widget)}.py"
        if example.exists() and GEN_SCREENSHOTS:
            png = File.generated(
                config=config,
                src_uri=f"images/{snake}.png",
                abs_src_path=snapshot(str(example)),
                inclusion=InclusionLevel.NOT_IN_NAV,
            )
            files.append(png)
            content = TEMPLATE.format(widget=widget, snake=snake, img=png.src_uri)
        else:
            # just a simple page
            content = f"# {widget}\n\n::: pymmcore_widgets.{widget}\n"
        file = File.generated(
            config,
            src_uri=os.path.join(root, f"{widget}.md"),
            content=content,
        )
        if file.src_uri in files.src_uris:
            files.remove(file)
            WIDGET_FILES.pop(widget, None)
        files.append(file)
        WIDGET_FILES[widget] = file
        logger.info("Created widget page: %s at %s", widget, file.src_uri)

    # cleanup
    from qtpy.QtWidgets import QApplication

    if app := QApplication.instance():
        app.quit()
        for _i in range(10):
            app.processEvents()
            time.sleep(0.01)


def on_nav(nav: Navigation, *, files: Files, config: MkDocsConfig) -> None:
    """Add pymmcore_widgets to the navigation."""
    top = next((sec.children for sec in nav if sec.title == "pymmcore-widgets"), nav)
    widget_section = next(sec for sec in top if sec.title == "Widgets")
    pages = [
        Page(name, file=file, config=config) for name, file in WIDGET_FILES.items()
    ]
    if not isinstance(widget_section, Section):
        raise RuntimeError(
            "Widget section not found, add navigation.indexes to theme.features."
        )
    widget_section.children.extend(pages)


SNAP = """
app = QApplication.instance()
app.processEvents()
widget = next(
    w for w in app.topLevelWidgets()
    if any(n in w.__class__.__module__ for n in ["pymmcore", "__main__"])
)
widget.setMinimumWidth(300)
app.processEvents()
widget.grab().save({})
"""


def snapshot(filename: str, sub: bool = False) -> str:
    """Run filename in a subprocess and snapshot top level widget.

    replace calls to `app.exec()` with a function that calls processEvents() and then
    grabs the top level widget, saving it to filename.
    """
    fpath = Path(filename)

    # create a temporary file to save the screenshot
    dest = mkstemp(prefix=fpath.stem, suffix=".png")[1]
    atexit.register(os.remove, dest)

    # replace the app.exec() call with a function that saves the screenshot
    new_exec = SNAP.format(repr(dest))
    src = fpath.read_text().strip()
    src = src.replace("app.exec_()", new_exec).replace("app.exec()", new_exec)
    src = src.replace("QApplication([])", "QApplication.instance() or QApplication([])")

    if sub:
        subprocess.run(["python", "-c", src], check=True)
    else:
        exec(src, {"__name__": "__main__", "__file__": str(fpath)})
        from pymmcore_plus.core import _mmcore_plus

        del _mmcore_plus._instance
        _mmcore_plus._instance = None

        if app := QApplication.instance():
            app.processEvents()
            for w in QApplication.topLevelWidgets():
                w.close()
                w.deleteLater()
            app.processEvents()
            app.processEvents()
    return dest
