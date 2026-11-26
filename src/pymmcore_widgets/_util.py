from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from psygnal import SignalGroup, SignalInstance
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QMarginsF, QObject, Qt
from qtpy.QtGui import QPainter, QPaintEvent, QPen, QResizeEvent
from qtpy.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

if TYPE_CHECKING:
    from collections.abc import Sequence
    from contextlib import AbstractContextManager
    from typing import Any


class ComboMessageBox(QDialog):
    """Dialog that presents a combo box of `items`."""

    def __init__(
        self,
        items: Sequence[str] = (),
        text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._combo = QComboBox()
        self._combo.addItems(items)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)

        self.setLayout(QVBoxLayout())
        if text:
            self.layout().addWidget(QLabel(text))
        self.layout().addWidget(self._combo)
        self.layout().addWidget(btn_box)

    def currentText(self) -> str:
        """Returns the current QComboBox text."""
        return self._combo.currentText()  # type: ignore [no-any-return]


def guess_channel_group(
    mmcore: CMMCorePlus | None = None, parent: QWidget | None = None
) -> str | None:
    """Try to update the list of channel group choices.

    1. get a list of potential channel groups from pymmcore
    2. if there is only one, use it, if there are > 1, show a dialog box
    """
    mmcore = mmcore or CMMCorePlus.instance()
    candidates = mmcore.getOrGuessChannelGroup()
    if len(candidates) == 1:
        return candidates[0]
    elif candidates:
        dialog = ComboMessageBox(candidates, "Select Channel Group:", parent=parent)
        if dialog.exec() == dialog.DialogCode.Accepted:
            return dialog.currentText()
    return None


def guess_objective_or_prompt(
    mmcore: CMMCorePlus | None = None, parent: QWidget | None = None
) -> str | None:
    """Try to update the list of objective choices.

    1. get a list of potential objective devices from pymmcore
    2. if there is only one, use it, if there are >1, show a dialog box
    """
    mmcore = mmcore or CMMCorePlus.instance()
    candidates = mmcore.guessObjectiveDevices()
    if len(candidates) == 1:
        return candidates[0]
    elif candidates:
        dialog = ComboMessageBox(candidates, "Select Objective Device:", parent=parent)
        if dialog.exec() == dialog.DialogCode.Accepted:
            return dialog.currentText()
    return None


def block_core(obj: Any) -> AbstractContextManager:
    """Block core signals."""
    if isinstance(obj, QObject):
        return signals_blocked(obj)  # type: ignore [no-any-return]
    if isinstance(obj, (SignalInstance, SignalGroup)):
        # (error in psygnal stubs)
        return obj.blocked()  # type: ignore [return-value]
    raise TypeError(f"Cannot block signals for {obj}")


def fov_kwargs(core: CMMCorePlus) -> dict:
    """Return image width and height in micron to be used for the grid plan."""
    if px := core.getPixelSizeUm():
        *_, width, height = core.getROI()
        return {"fov_width": (width * px) or None, "fov_height": (height * px) or None}
    return {}


# examples:
# "name_001" -> ("name", "001")
# "name" -> ("name", "")
# "name_001_002" -> ("name_001", "002")
# "name_02" -> ('name_02', None)
NUM_SPLIT = re.compile(r"(.*?)(?:_(\d{3,}))?$")
# A multi-position OME-TIFF is written as a folder named like the file without
# its extension, with one file per position (ome-writers).
OME_TIFF_EXTENSIONS = (".ome.tif", ".ome.tiff")


def _strip_counter(name: str) -> str:
    """Return the name without a "_###" counter at the end."""
    match = NUM_SPLIT.match(name)
    return match.group(1) if match else name


def get_next_available_path(requested_path: Path | str, min_digits: int = 3) -> Path:
    """Get the next available paths (filepath or folderpath if extension = "").

    This method adds a counter of min_digits to the filename or foldername to ensure
    that the path is unique.

    Parameters
    ----------
    requested_path : Path | str
        A path to a file or folder that may or may not exist.
    min_digits : int, optional
        The min_digits number of digits to be used for the counter. By default, 3.
    """
    if isinstance(requested_path, str):  # pragma: no cover
        requested_path = Path(requested_path)

    directory = requested_path.parent
    extension = requested_path.suffix
    # ome files like .ome.tiff or .ome.zarr are special,treated as a single extension
    if (stem := requested_path.stem).endswith(".ome"):
        extension = ".ome" + extension
        stem = stem[:-4]

    # look for ANY existing files in the folder that follow the pattern of
    # stem_###.extension
    # cannot use existing.stem because of the ome (2-part-extension) special case
    bases = [p.name.replace(extension, "") for p in directory.glob(f"*{extension}")]
    exists = requested_path.exists()

    # A multi-position OME-TIFF is a folder "stem" or "stem_###" instead.
    # Unlike files, a folder counts only if it has this stem: other folders are
    # not OME-TIFF output. Compared without case, so that "EXP_001" blocks
    # "exp_001" on case-insensitive file systems.
    if extension in OME_TIFF_EXTENSIONS and directory.is_dir():
        base_stem = _strip_counter(stem).casefold()
        for p in directory.iterdir():
            if p.is_dir() and _strip_counter(p.name).casefold() == base_stem:
                bases.append(p.name)
                exists = exists or p.name.casefold() == stem.casefold()

    current_max = 0
    for base in bases:
        # if the base name ends with a number, increase the current_max
        if (match := NUM_SPLIT.match(base)) and (num := match.group(2)):
            current_max = max(int(num), current_max)
            # if it has more digits than expected, update the ndigits
            if len(num) > min_digits:
                min_digits = len(num)

    # if the path does not exist and there are no existing files,
    # return the requested path
    if not exists and current_max == 0:
        return requested_path

    current_max += 1
    # otherwise return the next path greater than the current_max
    # remove any existing counter from the stem
    if match := NUM_SPLIT.match(stem):
        stem, num = match.groups()
        if num:
            # if the requested path has a counter that is greater than any other files
            # use it
            current_max = max(int(num), current_max)
    return directory / f"{stem}_{current_max:0{min_digits}d}{extension}"


class SeparatorWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(1)

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        painter = QPainter(self)
        painter.setPen(QPen(Qt.GlobalColor.gray, 1, Qt.PenStyle.SolidLine))
        painter.drawLine(self.rect().topLeft(), self.rect().topRight())


class ResizingGraphicsView(QGraphicsView):
    """A QGraphicsView that resizes the scene to fit the view."""

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.padding = 0.05  # fraction of the bounding rect

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        if not (scene := self.scene()):
            return
        rect = scene.itemsBoundingRect()
        xmargin = rect.width() * self.padding
        ymargin = rect.height() * self.padding
        margins = QMarginsF(xmargin, ymargin, xmargin, ymargin)
        self.fitInView(rect.marginsAdded(margins), Qt.AspectRatioMode.KeepAspectRatio)
        super().resizeEvent(event)


def load_system_config(config: str = "", mmcore: CMMCorePlus | None = None) -> None:
    """Internal convenience for `loadSystemConfiguration(config)`.

    This also unloads all devices first and resets the STATE.
    If config is `None` or empty string, will load the MMConfig_demo.
    Note that it should also always be fine for the end-user to use something like
    `CMMCorePlus.instance().loadSystemConfiguration(...)` (instead of this function)
    and we need to handle that as well.  So this function shouldn't get too complex.
    """
    mmc = mmcore or CMMCorePlus.instance()
    mmc.unloadAllDevices()
    mmc.loadSystemConfiguration(config or "MMConfig_demo.cfg")
