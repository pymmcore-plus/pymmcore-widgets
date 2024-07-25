from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QAbstractGraphicsShapeItem, QVBoxLayout, QWidget

from pymmcore_widgets.useq_widgets._well_plate_widget import (
    WellPlateView,
)

if TYPE_CHECKING:
    import useq
    from qtpy.QtGui import QMouseEvent


class _WellPlateView(WellPlateView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setDragMode(self.DragMode.NoDrag)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton:
            for item in self.items(event.pos()):
                if isinstance(item, QAbstractGraphicsShapeItem):
                    x, y = event.pos().x() * 1000, event.pos().y() * 1000
                    print(x, y, item.boundingRect().center())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        return

    def drawPlate(self, plan: useq.WellPlate | useq.WellPlatePlan) -> None:
        """Draw the well plate on the view."""
        super().drawPlate(plan)


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


if __name__ == "__main__":
    import useq
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    mmc = CMMCorePlus.instance()
    plate = useq.WellPlate.from_str("96-well")
    wdg = PlateTestWidget(mmcore=mmc)
    wdg.set_plate(plate)
    wdg.show()
    app.exec()
