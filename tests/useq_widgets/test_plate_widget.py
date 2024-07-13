from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import qtpy
import useq
from qtpy.QtCore import Qt
from qtpy.QtGui import QMouseEvent

from pymmcore_widgets.useq_widgets import WellPlateWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

WELL_96 = useq.WellPlate.from_str("96-well")
CUSTOM_PLATE = useq.WellPlate(
    name="custom",
    rows=8,
    columns=12,
    circular_wells=False,
    well_size=(13, 10),
    well_spacing=(18, 18),
)

BASIC_PLAN = useq.WellPlatePlan(
    plate="96-well",
    a1_center_xy=(0, 0),
    selected_wells=slice(0, 8, 2),
)

ROTATED_PLAN = BASIC_PLAN.model_copy(update={"rotation": 10})


@pytest.mark.parametrize("plan", [BASIC_PLAN, ROTATED_PLAN, CUSTOM_PLATE])
def test_plate_widget(qtbot: QtBot, plan: Any) -> None:
    wdg = WellPlateWidget(plan)
    qtbot.addWidget(wdg)
    wdg.show()
    val = wdg.value()
    if isinstance(plan, useq.WellPlate):
        val = val.plate  # type: ignore
    assert val == plan


def test_plate_widget_selection(qtbot: QtBot) -> None:
    wdg = WellPlateWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    # Ensure that if no plate is provided when instantiating the widget, the currently
    # selected plate in the combobox is used.
    assert wdg._view.scene().items()

    wdg.plate_name.setCurrentText("96-well")
    wdg.setCurrentSelection((slice(0, 4, 2), (1, 2)))
    selection = wdg.currentSelection()
    assert selection == ((0, 1), (0, 2), (2, 1), (2, 2))


@pytest.mark.skipif(qtpy.QT5, reason="QMouseEvent API changed")
def test_plate_mouse_press(qtbot: QtBot) -> None:
    wdg = WellPlateWidget()
    qtbot.addWidget(wdg)
    wdg.show()
    wdg.plate_name.setCurrentText("96-well")

    # press
    assert wdg._view._pressed_item is None
    assert not wdg._view._selected_items
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        wdg.rect().translated(10, 0).center().toPointF(),
        wdg.rect().translated(10, 0).center().toPointF(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    wdg._view.mousePressEvent(event)

    assert wdg._view._pressed_item is not None

    # release
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        wdg.rect().translated(10, 0).center().toPointF(),
        wdg.rect().translated(10, 0).center().toPointF(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    wdg._view.mouseReleaseEvent(event)

    assert wdg._view._pressed_item is None
    assert len(wdg._view._selected_items) == 1

    # simulate rubber band on full widget, should select all
    with qtbot.waitSignal(wdg._view.selectionChanged):
        wdg._view._on_rubber_band_changed(wdg.rect())
    assert len(wdg._view._selected_items) == 96

    # simulate opt-click rubber band on full widget, should clear selection
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        wdg.rect().translated(10, 0).center().toPointF(),
        wdg.rect().translated(10, 0).center().toPointF(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.AltModifier,
    )
    wdg._view.mousePressEvent(event)

    # simulate rubber band on full widget
    with qtbot.waitSignal(wdg._view.selectionChanged):
        wdg._view._on_rubber_band_changed(wdg.rect())
    assert len(wdg._view._selected_items) == 0
