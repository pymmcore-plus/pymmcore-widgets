from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda.handlers import TensorStoreHandler
from useq import MDASequence

from pymmcore_widgets._stack_viewer_v2._mda_viewer import MDAViewer

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


@pytest.mark.allow_leaks
def test_mda_viewer(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    core = global_mmcore
    core.defineConfig("Channel", "DAPI", "Camera", "Mode", "Artificial Waves")
    core.defineConfig("Channel", "DAPI", "Camera", "StripeWidth", "1")
    core.defineConfig("Channel", "FITC", "Camera", "Mode", "Artificial Waves")
    core.defineConfig("Channel", "FITC", "Camera", "StripeWidth", "4")

    sequence = MDASequence(
        channels=({"config": "DAPI", "exposure": 1}, {"config": "FITC", "exposure": 1}),
        stage_positions=[(0, 0), (1, 1)],
        z_plan={"range": 9, "step": 0.4},
        time_plan={"interval": 0.2, "loops": 4},
        # grid_plan={"rows": 2, "columns": 1},
    )
    v = MDAViewer()
    qtbot.addWidget(v)
    assert isinstance(v.data, TensorStoreHandler)

    core.mda.run(sequence, output=v.data)
    assert v.data.current_sequence is sequence
