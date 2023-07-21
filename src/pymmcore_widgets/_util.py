from __future__ import annotations

from datetime import timedelta
from typing import ContextManager, Sequence

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
from useq import AnyGridPlan, MDASequence


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


def _select_output_unit(duration: float) -> tuple[float, str]:
    if duration < 1.0:
        return duration * 1000, "ms"
    elif duration < 60.0:
        return duration, "sec"
    elif duration < 3600.0:
        return duration / 60, "min"
    else:
        return duration / 3600, "hours"


def block_core(mmcore_events: CMMCoreSignaler | PCoreSignaler) -> ContextManager:
    """Block core signals."""
    if isinstance(mmcore_events, CMMCoreSignaler):
        return mmcore_events.blocked()  # type: ignore
    elif isinstance(mmcore_events, PCoreSignaler):
        return signals_blocked(mmcore_events)  # type: ignore


def fmt_timedelta(time: timedelta) -> str:
    """Take timedelta and return formatted string.

    Examples
    --------
    >>> fmt_timedelta(timedelta(seconds=100))
    '01 min  40 sec'
    >>> fmt_timedelta(timedelta(minutes=320, seconds=2500))
    '06 hours  01 min  40 sec'
    """
    d = "day" if time.days == 1 else "days"
    _time = str(time).replace(f" {d}, ", ":") if time.days >= 1 else f"0:{time!s}"
    out: list = []
    keys = ["days", "hours", "min", "sec", "ms"]
    for i, t in enumerate(_time.split(":")):
        if i == 3:
            s = t.split(".")
            if len(s) == 2:
                sec = f"{int(s[0]):02d} sec " if int(s[0]) > 0 else ""
                ms = f"{int(s[1][:3]):03d} ms" if int(s[1][:3]) > 0 else ""
                out.append(f"{sec}{ms}")
            else:
                out.append(f"{int(s[0]):02d} sec") if int(s[0]) > 0 else ""
        else:
            out.append(f"{int(float(t)):02d} {keys[i]}") if int(float(t)) > 0 else ""
    return "  ".join(out)


def get_grid_type(grid: dict) -> AnyGridPlan | None:
    """Get the grid type from the grid_plan."""
    return MDASequence(grid_plan=grid).grid_plan
