from __future__ import annotations

import contextlib
from pathlib import Path
from textwrap import indent
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QFrame, QWidget

if TYPE_CHECKING:
    from mkdocs_macros.plugin import MacrosPlugin

EXAMPLES = Path(__file__).parent.parent / "examples"
IMAGES = Path(__file__).parent / "_auto_images"
IMAGES.mkdir(exist_ok=True, parents=True)


def define_env(env: MacrosPlugin) -> None:
    """Define the environment for the docs."""

    @env.macro
    def include_example(path: str, width: int | None = None) -> str:
        example = EXAMPLES / path
        src = example.read_text().strip()
        markdown = f"```python\n{src}\n```\n"

        return markdown

    @env.macro
    def show_image(path: str, width: int | None = None) -> str:
        example = EXAMPLES / path
        src = example.read_text().strip()
        image = IMAGES / f"{example.stem}.png"
        if not image.exists():
            _make_image(src, str(image), width)
        return f" ![{example.stem}](../../_auto_images/{image.name}){{ width={width}}}"


def _make_image(source_code: str, dest: str, width=None):
    """Grab the top widgets of the application."""
    print(f"*** MAKING {dest.split('/')[-1]} ...")

    # keep same CMMCorePlus and load configuration once for all widgets
    mmc = CMMCorePlus.instance()
    if len(mmc.getLoadedDevices()) <= 1:
        mmc.loadSystemConfiguration()

    _to_exec = source_code.replace(
        "QApplication([])", "QApplication.instance() or QApplication([])"
    )
    _to_exec = _to_exec.replace("mmc.loadSystemConfiguration()", "")
    _to_exec = _to_exec.replace("app.exec_()", "")

    if "class " in _to_exec:
        # return
        _import = indent(_to_exec[: _to_exec.index("class ") - 3], "        ")
        try:
            _super_index = _to_exec.index("super().__init__(parent)")
            idx = 24
        except ValueError:
            _super_index = _to_exec.index("super().__init__()")
            idx = 18
        top = _to_exec[: _super_index + idx]
        bottom = _to_exec[_super_index + idx :]
        new = f"{top}\n{_import}\n{bottom}"
        _to_exec = _to_exec.replace(_to_exec, new)

    exec(_to_exec)

    w0 = QApplication.instance() or QApplication([])
    w = _w(w0)
    w.activateWindow()
    if width:
        w.setFixedWidth(width)
    w.grab().save(dest)
    with contextlib.suppress(AttributeError):
        w._disconnect()
    w.close()


def _w(w0: QApplication) -> QWidget:  # sourcery skip: use-next
    if len(w0.topLevelWidgets()) == 1:
        return w0.topLevelWidgets()[0]
    for wdg in w0.topLevelWidgets():
        if not isinstance(wdg, QFrame) or not isinstance(wdg, QWidget):
            return wdg
