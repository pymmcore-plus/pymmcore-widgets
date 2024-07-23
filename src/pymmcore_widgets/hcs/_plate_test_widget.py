from __future__ import annotations

import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QVBoxLayout, QWidget

from pymmcore_widgets.useq_widgets._well_plate_widget import WellPlateView


class _WellPlateView(WellPlateView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setDragMode(self.DragMode.NoDrag)

    def drawPlate(self, plate: useq.WellPlate | useq.WellPlatePlan) -> None:
        """Draw the plate on the view."""
        super().drawPlate(plate)

        if isinstance(plate, useq.WellPlatePlan):
            plate = plate.plate

        self.setSelectedIndices([(0, 0), (0, plate.columns - 1)])


class PlateTestWidget(QWidget):
    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._plate_view = _WellPlateView(self)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._plate_view)

    def set_plate(self, plate: useq.WellPlate | useq.WellPlatePlan) -> None:
        """Set the plate to be displayed."""
        self._plate_view.drawPlate(plate)
