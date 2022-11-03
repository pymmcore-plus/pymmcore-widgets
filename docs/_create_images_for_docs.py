from __future__ import annotations

from pathlib import Path
from textwrap import indent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

EXAMPLES = Path(__file__).parent.parent / "examples"
IMAGES = Path(__file__).parent / "_auto_images"
IMAGES.mkdir(exist_ok=True, parents=True)


def make_image(path: str, width=None):
    """Grab the top widgets of the application."""
    from qtpy.QtWidgets import QApplication

    example = EXAMPLES / path
    source_code = example.read_text().strip()
    image = IMAGES / f"{example.stem}.png"
    dest = str(image)

    print("MAKING IMAGE...")

    _to_exec = source_code.replace(
        "QApplication([])", "QApplication.instance() or QApplication([])"
    ).replace("app.exec_()", "")

    if "class" in _to_exec:
        _import = indent(_to_exec[: _to_exec.index("class") - 3], "        ")
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

    w = QApplication.topLevelWidgets()[-1]
    w.activateWindow()
    if width:
        w.setFixedWidth(width)
    w.grab().save(dest)
    w.close()

    print("IMAGE SAVED...")


make_image("image_widget.py")
