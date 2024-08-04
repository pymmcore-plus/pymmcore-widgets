from __future__ import annotations

from typing import TYPE_CHECKING

import useq

from pymmcore_widgets.hcs._plate_navigator_widget import (
    DATA_POSITION,
    PlateNavigatorWidget,
    _PresetPositionItem,
)

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


wp96 = useq.WellPlate.from_str("96-well")


def test_plate_navigator_widget(qtbot: QtBot, global_mmcore: CMMCorePlus):
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

    # get all the items of type _PresetPositionItem
    preset_items = [
        item
        for item in reversed(scene.items())
        if isinstance(item, _PresetPositionItem)
    ]
    # make sure the stored positions for a1 are correct
    a1 = preset_items[:5]
    pos = [item.data(DATA_POSITION) for item in a1]
    assert [(p.x, p.y) for p in pos] == [
        (0.0, 0.0),
        (-3200.0, 0.0),
        (3200.0, 0.0),
        (0.0, -3200.0),
        (0.0, 3200.0),
    ]
    # make sure the stored positions for h12 are correct
    h12 = preset_items[-5:]
    pos = [item.data(DATA_POSITION) for item in h12]
    assert [(p.x, p.y) for p in pos] == [
        (99000.0, -63000.0),
        (95800.0, 63000.0),
        (102200.0, 63000.0),
        (99000.0, 59800.0),
        (99000.0, 66200.0),
    ]
