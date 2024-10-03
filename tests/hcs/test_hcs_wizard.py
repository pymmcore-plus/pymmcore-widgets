from __future__ import annotations

from typing import TYPE_CHECKING

import useq

from pymmcore_widgets.hcs import HCSWizard

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_hcs_wizard(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    """Test the HCSWizard."""

    plan = useq.WellPlatePlan(
        plate="96-well",
        a1_center_xy=(1000, 1500),
        rotation=0.3,
        selected_wells=slice(0, 8, 2),
    )

    wdg = HCSWizard(mmcore=global_mmcore)
    wdg.setValue(plan)
    qtbot.addWidget(wdg)
    wdg.show()
    wdg.next()
    wdg.next()
    wdg.next()
    wdg.accept()

    # we haven't done anything, the plan should be the same
    assert wdg.value() == plan
