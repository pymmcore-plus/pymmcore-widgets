from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pymmcore_plus import CMMCorePlus

from pymmcore_widgets.useq_widgets._zplan_widget import Mode, ZPlanWidget

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget


class CoreConnectedZPlanWidget(ZPlanWidget):
    """[ZPlanWidget](../ZPlanWidget#) connected to a Micro-Manager core instance.

    Parameters
    ----------
    mmcore : CMMCorePlus | None
        Optional [`CMMCorePlus`][pymmcore_plus.CMMCorePlus] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    parent : QWidget | None
        Optional parent widget, by default None.
    """

    def __init__(
        self, mmcore: CMMCorePlus | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._mmc = mmcore or CMMCorePlus.instance()

        self._btn_mark_top.clicked.connect(self._mark_top)
        self._btn_mark_bot.clicked.connect(self._mark_bottom)

    def setMode(
        self,
        mode: Mode | Literal["top_bottom", "range_around", "above_below"],
    ) -> None:
        super().setMode(mode)
        is_tb = self._mode == Mode.TOP_BOTTOM
        self._btn_mark_top.setVisible(is_tb)
        self._btn_mark_bot.setVisible(is_tb)

    def _mark_top(self) -> None:
        self.top.setValue(self._mmc.getZPosition())

    def _mark_bottom(self) -> None:
        self.bottom.setValue(self._mmc.getZPosition())
