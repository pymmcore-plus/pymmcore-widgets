from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus

from pymmcore_widgets.useq_widgets._z import ROW_TOP_BOTTOM, Mode, ZPlanWidget

from ._xy_bounds import MarkVisit

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
        self.bottom_btn = MarkVisit(
            MDI6.arrow_collapse_down, mark_text="Mark Bottom", icon_size=16
        )
        self.top_btn = MarkVisit(
            MDI6.arrow_collapse_up, mark_text="Mark Top", icon_size=16
        )

        super().__init__(parent)
        self._mmc = mmcore or CMMCorePlus.instance()

        self.bottom_btn.mark.clicked.connect(self._mark_bottom)
        self.top_btn.mark.clicked.connect(self._mark_top)
        self.bottom_btn.visit.clicked.connect(self._visit_bottom)
        self.top_btn.visit.clicked.connect(self._visit_top)

        row = ROW_TOP_BOTTOM + 1  # --------------- Bottom / Top parameters
        self._grid_layout.addWidget(self.bottom_btn, row, 1)
        self._grid_layout.addWidget(self.top_btn, row, 4)

    def setMode(
        self,
        mode: Mode | Literal["top_bottom", "range_around", "above_below"] | None = None,
    ) -> None:
        super().setMode(mode)
        self.bottom_btn.setVisible(self._mode == Mode.TOP_BOTTOM)
        self.top_btn.setVisible(self._mode == Mode.TOP_BOTTOM)

    def _mark_bottom(self) -> None:
        self.bottom.setValue(self._mmc.getZPosition())

    def _mark_top(self) -> None:
        self.top.setValue(self._mmc.getZPosition())

    def _visit_bottom(self) -> None:
        self._mmc.setZPosition(self.bottom.value())

    def _visit_top(self) -> None:
        self._mmc.setZPosition(self.top.value())
