from __future__ import annotations

from typing import TYPE_CHECKING

import useq

from pymmcore_widgets.hcs._plate_navigator_widget import PlateNavigatorWidget

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
