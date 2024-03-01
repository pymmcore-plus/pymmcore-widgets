from __future__ import annotations

from pathlib import Path
from typing import ContextManager, Sequence

import useq
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.core.events import CMMCoreSignaler, PCoreSignaler
from qtpy.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked


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
        if dialog.exec_() == dialog.DialogCode.Accepted:
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
        if dialog.exec_() == dialog.DialogCode.Accepted:
            return dialog.currentText()
    return None


def block_core(mmcore_events: CMMCoreSignaler | PCoreSignaler) -> ContextManager:
    """Block core signals."""
    if isinstance(mmcore_events, CMMCoreSignaler):
        return mmcore_events.blocked()  # type: ignore
    elif isinstance(mmcore_events, PCoreSignaler):
        return signals_blocked(mmcore_events)  # type: ignore


def cast_grid_plan(
    grid: dict | useq.GridRowsColumns | useq.GridWidthHeight | useq.GridFromEdges,
) -> useq.GridRowsColumns | useq.GridWidthHeight | useq.GridFromEdges | None:
    """Get the grid type from the grid_plan."""
    if not grid or isinstance(grid, useq.RandomPoints):
        return None
    if isinstance(grid, dict):
        _grid = useq.MDASequence(grid_plan=grid).grid_plan
        return None if isinstance(_grid, useq.RandomPoints) else _grid
    return grid


def fov_kwargs(core: CMMCorePlus) -> dict:
    """Return image width and height in micron to be used for the grid plan."""
    if px := core.getPixelSizeUm():
        *_, width, height = core.getROI()
        return {"fov_width": (width * px) or None, "fov_height": (height * px) or None}
    return {}


def _get_next_available_path(
    path: Path | str, extension: str, ndigits: int = 3
) -> Path:
    """Get the next available paths (filepath or folderpath if extension = "").

    This method adds a counter of ndigits to the filename or foldername to ensure
    that the path is unique.

    Parameters
    ----------
    path : Path | str
        The starting path without extension (e.g./User/Desktop/Folder/Filename).
    extension : str
        The extension to be used (e.g. ".ome.tiff").
    ndigits : int (optional)
        The number of digits to be used for the counter. By default, 3.
    """
    # if the extension does not start with a dot, add it
    if not extension.startswith("."):
        extension = f".{extension}"

    if isinstance(path, str):
        path = Path(path)

    # remove extension from the path if any
    if str(path).endswith(extension):
        path = Path(str(path).replace(extension, ""))

    stem = path.stem

    # remove digits from the stem if any
    cur_num = stem.rsplit("_")[-1]
    if cur_num.isdigit() and len(cur_num) == ndigits:
        stem = stem[: -ndigits - 1]

    current_max = 1

    # find the current maximum number
    current_files = path.parent.glob(f"*{extension}")
    for fn in current_files:
        try:
            if extension in str(fn):
                fn = Path(str(fn).replace(extension, ""))
            current_max = max(current_max, int(fn.stem.rsplit("_")[-1]))
        except ValueError:
            continue

    # find the first available path
    new_path = path.parent / f"{stem}{extension}"
    if new_path.exists():
        # If the path exists, find the next available filename
        while True:
            number = f"_{current_max:0{ndigits}d}"
            new_path = path.parent / f"{stem}{number}{extension}"

            if not new_path.exists():
                break

            current_max += 1

    return new_path
