from __future__ import annotations

import contextlib
from pathlib import Path

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QFrame, QWidget

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

    mmc = CMMCorePlus.instance()
    if len(mmc.getLoadedDevices()) <= 1:
        mmc.loadSystemConfiguration()

    _to_exec = source_code.replace(
        "QApplication([])", "QApplication.instance() or QApplication([])"
    )
    _to_exec = _to_exec.replace("mmc.loadSystemConfiguration()", "")
    _to_exec = _to_exec.replace("app.exec_()", "")

    if "class " in _to_exec:
        return
        # _import = indent(_to_exec[: _to_exec.index("class ") - 3], "        ")
        # try:
        #     _super_index = _to_exec.index("super().__init__(parent)")
        #     idx = 24
        # except ValueError:
        #     _super_index = _to_exec.index("super().__init__()")
        #     idx = 18
        # top = _to_exec[: _super_index + idx]
        # bottom = _to_exec[_super_index + idx :]
        # new = f"{top}\n{_import}\n{bottom}"
        # _to_exec = _to_exec.replace(_to_exec, new)

    exec(_to_exec)

    w0 = QApplication.instance() or QApplication([])
    w = _w(w0)
    w.activateWindow()
    if width:
        w.setFixedWidth(width)
    w.grab().save(dest)
    w.close()
    with contextlib.suppress(AttributeError):
        w._disconnect()


def _w(w0: QApplication) -> QWidget:  # sourcery skip: use-next
    if len(w0.topLevelWidgets()) == 1:
        return w0.topLevelWidgets()[0]
    for wdg in w0.topLevelWidgets():
        if not isinstance(wdg, QFrame) or not isinstance(wdg, QWidget):
            return wdg

    return None


img_name_list = [f.stem for f in IMAGES.iterdir()]
for wdg in EXAMPLES.iterdir():
    if wdg.stem in img_name_list:
        continue
    print(f"*** MAKING {wdg.stem}.png ...")
    make_image(f"{wdg.stem}.py")

# make_image("live_button.py")
