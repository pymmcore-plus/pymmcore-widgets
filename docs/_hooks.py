from __future__ import annotations

import atexit
import os
import subprocess
import time
from pathlib import Path
from tempfile import mkstemp
from typing import TYPE_CHECKING, cast

from mkdocs.plugins import get_plugin_logger
from mkdocs.structure.files import File, Files, InclusionLevel
from qtpy.QtWidgets import QApplication, QWidget

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


WIDGET_PAGE_TEMPLATE = """
# {widget}

<figure markdown>
  ![{widget} widget](/{img_uri}){{ loading=lazy, class="widget-image" }}
  <figcaption>
    This image generated from <a href="#example">example code below</a>.
  </figcaption>
</figure>

::: pymmcore_widgets.{widget}
    options:
      heading_level: 2
      show_source: false

## Example

```python linenums="1" title="{snake}.py"
{src}
```
"""


def _look_for_section(sections: list, title: str = "Widgets") -> dict | None:
    """Look for the 'Widgets' section in the navigation."""
    for section in sections:
        if isinstance(section, dict):
            if set(section) == {title}:
                return section
            for _key, value in section.items():
                if isinstance(value, list):
                    if (result := _look_for_section(value, title)) is not None:
                        return result
        if isinstance(section, list):
            if (result := _look_for_section(section, title)) is not None:
                return result
    return None


def on_files(files: Files, /, *, config: MkDocsConfig) -> None:
    if not (widget_section := _look_for_section(cast("list", config.nav), "Widgets")):
        raise RuntimeError("Could not find 'Widgets' section in navigation.")
    widget_contents = widget_section["Widgets"]
    PAGES_TO_GENERATE = {}
    for item in widget_contents:
        if isinstance(item, dict):
            for key, value in item.items():
                PAGES_TO_GENERATE[key] = value

    for widget, src_uri in PAGES_TO_GENERATE.items():
        logger.info("Generating widget page for %s at %s ...", widget, src_uri)
        snake = _camel_to_snake(widget)
        example = EXAMPLES / f"{_camel_to_snake(widget)}.py"
        if example.exists() and GEN_SCREENSHOTS:
            png = File.generated(
                config=config,
                src_uri=src_uri.replace(".md", ".png"),
                abs_src_path=snapshot(str(example)),
                inclusion=InclusionLevel.NOT_IN_NAV,
            )
            files.append(png)
            content = WIDGET_PAGE_TEMPLATE.format(
                widget=widget,
                snake=snake,
                img_uri=png.src_uri,
                src=example.read_text(),
            )
        else:
            # just a simple page
            content = f"# {widget}\n\n::: pymmcore_widgets.{widget}\n"

        file = File.generated(
            config,
            src_uri=src_uri,
            content=content,
        )
        if file.src_uri in files.src_uris:
            files.remove(file)
        files.append(file)

    # cleanup
    from qtpy.QtWidgets import QApplication

    if app := QApplication.instance():
        app.quit()
        for _i in range(10):
            app.processEvents()
            time.sleep(0.01)


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


# sub=True is slower... but sub=False is still prone to picking the wrong
# top widget to show...
def snapshot(filename: str, sub: bool = True) -> str:
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
