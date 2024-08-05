from __future__ import annotations

from typing import TYPE_CHECKING

import useq
from qtpy.QtCore import QPointF, Qt

from pymmcore_widgets.hcs._plate_navigator_widget import (
    DATA_POSITION,
    PlateNavigatorWidget,
    _PresetPositionItem,
)

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


wp96 = useq.WellPlate.from_str("96-well")
wp384 = useq.WellPlate.from_str("384-well")


def test_plate_navigator_widget_circular(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PlateNavigatorWidget(mmcore=global_mmcore)
    qtbot.addWidget(wdg)
    wdg.show()

    scene = wdg._plate_view._scene
    assert not scene.items()

    wdg.set_plan(wp96)
    assert scene.items()
    # assert correct number of items
    # 96 * 3 (_HoverWellItem, QGraphicsEllipseItem, QGraphicsTextItem)
    assert len(scene.items()) == 288

    # toggle preset movements checkbox
    wdg._on_preset_movements_toggled(True)
    assert scene.items()
    # assert correct number of items
    # 96 * 11 (QGraphicsEllipseItem * 6, _PresetPositionItem * 5)
    assert len(scene.items()) == 1056


def test_plate_navigator_widget_rectangular(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PlateNavigatorWidget(mmcore=global_mmcore)
    qtbot.addWidget(wdg)
    wdg.show()

    scene = wdg._plate_view._scene
    assert not scene.items()

    wdg.set_plan(wp384)
    assert scene.items()
    # assert correct number of items
    # 384 * 3 (_HoverWellItem, QGraphicsRectItem, QGraphicsTextItem)
    assert len(scene.items()) == 1152

    # toggle preset movements checkbox
    wdg._on_preset_movements_toggled(True)
    assert scene.items()
    # assert correct number of items
    # 384 * 11 (QGraphicsRectItem * 6, _PresetPositionItem * 5)
    assert len(scene.items()) == 4224


def test_hover_item(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PlateNavigatorWidget(mmcore=global_mmcore)
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.set_plan(wp96)
    scene = wdg._plate_view._scene

    # get the _HoverWellItem for A1
    a1_hover_well = list(reversed(scene.items()))[96]
    assert a1_hover_well._current_position is None
    assert a1_hover_well.data(DATA_POSITION) == useq.AbsolutePosition(
        x=0.0, y=0.0, name="A1"
    )

    # simulate mouse double-click on center of A1 well
    global_mmcore.setXYPosition(100, 100)
    global_mmcore.waitForSystem()
    assert round(global_mmcore.getXPosition()) == 100
    assert round(global_mmcore.getYPosition()) == 100
    center_pos = a1_hover_well.boundingRect().center()
    scene_pos = a1_hover_well.mapToScene(center_pos)
    view_pos = wdg._plate_view.mapFromScene(scene_pos)
    qtbot.mouseDClick(
        wdg._plate_view.viewport(), Qt.MouseButton.LeftButton, pos=view_pos
    )
    global_mmcore.waitForSystem()
    assert a1_hover_well._current_position == (0.0, 0.0)
    assert global_mmcore.getXPosition() == 0
    assert global_mmcore.getYPosition() == 0


def test_preset_position_item(qtbot: QtBot, global_mmcore: CMMCorePlus):
    wdg = PlateNavigatorWidget(mmcore=global_mmcore)
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.set_plan(wp96)
    # toggle preset movements checkbox
    wdg._on_preset_movements_toggled(True)

    # get all the items of type _PresetPositionItem
    preset_items = [
        item
        for item in reversed(wdg._plate_view._scene.items())
        if isinstance(item, _PresetPositionItem)
    ]

    # get the item for A1
    a1 = preset_items[:5]
    # make sure the stored positions for a1 are correct
    a1_pos = [item.data(DATA_POSITION) for item in a1]
    assert [(p.x, p.y) for p in a1_pos] == [
        (0.0, 0.0),
        (-3200.0, 0.0),
        (3200.0, 0.0),
        (0.0, -3200.0),
        (0.0, 3200.0),
    ]

    # get the item for H12
    h12 = preset_items[-5:]
    # make sure the stored positions for h12 are correct
    h12_pos = [item.data(DATA_POSITION) for item in h12]
    assert [(p.x, p.y) for p in h12_pos] == [
        (99000.0, -63000.0),
        (95800.0, 63000.0),
        (102200.0, 63000.0),
        (99000.0, 59800.0),
        (99000.0, 66200.0),
    ]

    # simulate mouse double-click on edge of A1 well
    global_mmcore.setXYPosition(100, 100)
    global_mmcore.waitForSystem()
    assert round(global_mmcore.getXPosition()) == 100
    assert round(global_mmcore.getYPosition()) == 100

    right_edge = a1_pos[2]
    scene_pos = QPointF(right_edge.x, right_edge.y)
    view_pos = wdg._plate_view.mapFromScene(scene_pos)
    qtbot.mouseDClick(
        wdg._plate_view.viewport(), Qt.MouseButton.LeftButton, pos=view_pos
    )
    global_mmcore.waitForSystem()
    assert round(global_mmcore.getXPosition()) == 3200
    assert round(global_mmcore.getYPosition()) == 0
