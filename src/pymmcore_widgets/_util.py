from __future__ import annotations

import re
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


# examples:
# "name_001" -> ("name", "001")
# "name" -> ("name", "")
# "name_001_002" -> ("name_001", "002")
# "name_02" -> ('name_02', None)
NUM_SPLIT = re.compile(r"(.*?)(?:_(\d{3,}))?$")


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
    current_max = 0
    for existing in directory.glob(f"*{extension}"):
        # cannot use existing.stem because of the ome (2-part-extension) special case
        base = existing.name.replace(extension, "")
        # if the base name ends with a number, increase the current_max
        if (match := NUM_SPLIT.match(base)) and (num := match.group(2)):
            current_max = max(int(num), current_max)
            # if it has more digits than expected, update the ndigits
            if len(num) > min_digits:
                min_digits = len(num)

    # if the path does not exist and there are no existing files,
    # return the requested path
    if not requested_path.exists() and current_max == 0:
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
