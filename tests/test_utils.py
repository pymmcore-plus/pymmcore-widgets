from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import QCoreApplication, QPoint, QPointF, Qt
from qtpy.QtGui import QWheelEvent
from qtpy.QtWidgets import QApplication, QComboBox
from superqt import QDoubleSlider

from pymmcore_widgets._util import NoWheelTableWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


WHEEL_UP = QWheelEvent(
    QPointF(0, 0),  # pos
    QPointF(0, 0),  # globalPos
    QPoint(0, 0),  # pixelDelta
    QPoint(0, 120),  # angleDelta
    Qt.MouseButton.NoButton,  # buttons
    Qt.KeyboardModifier.NoModifier,  # modifiers
    Qt.ScrollPhase.NoScrollPhase,  # phase
    False,  # inverted
)


def test_no_wheel_table_scroll(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    tbl = NoWheelTableWidget()
    qtbot.addWidget(tbl)
    tbl.show()

    # Create enough widgets to scroll
    sb = tbl.verticalScrollBar()
    assert sb is not None
    while sb.maximum() == 0:
        new_row = tbl.rowCount()
        tbl.insertRow(new_row)
        tbl.setCellWidget(new_row, 0, QComboBox(tbl))
        QApplication.processEvents()

    # Test Combo Box
    combo = QComboBox(tbl)
    combo.addItems(["combo0", "combo1", "combo2"])
    combo.setCurrentIndex(1)
    combo_row = tbl.rowCount()
    tbl.insertRow(combo_row)
    tbl.setCellWidget(combo_row, 0, combo)

    sb.setValue(sb.maximum())
    # Synchronous event emission and allows us to pass through the event filter
    QCoreApplication.sendEvent(combo, WHEEL_UP)
    # Assert the table widget scrolled but the combo didn't change
    assert sb.value() < sb.maximum()
    assert combo.currentIndex() == 1

    # Test Slider
    slider = QDoubleSlider(tbl)
    slider.setRange(0, 1)
    slider.setValue(0)
    slider_row = tbl.rowCount()
    tbl.insertRow(slider_row)
    tbl.setCellWidget(slider_row, 0, slider)

    sb.setValue(sb.maximum())
    # Synchronous event emission and allows us to pass through the event filter
    QCoreApplication.sendEvent(slider, WHEEL_UP)
    # Assert the table widget scrolled but the slider didn't change
    assert sb.value() < sb.maximum()
    assert slider.value() == 0

    # I can't know how to hear any more about tables
    tbl.close()
