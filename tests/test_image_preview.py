from typing import TYPE_CHECKING

import numpy as np
import useq
from pymmcore_plus import CMMCorePlus

from pymmcore_widgets import ImagePreview

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_image_preview(qtbot: "QtBot"):
    """Test that the exposure widget works."""
    mmcore = CMMCorePlus.instance()
    widget = ImagePreview()
    qtbot.addWidget(widget)
    assert widget._mmc is mmcore

    with qtbot.waitSignal(mmcore.events.imageSnapped):
        mmcore.snap()
    img = widget._canvas.render()

    with qtbot.waitSignal(mmcore.events.imageSnapped):
        mmcore.snap()
    img2 = widget._canvas.render()

    assert not np.allclose(img, img2)

    assert not widget.streaming_timer.isActive()
    mmcore.startContinuousSequenceAcquisition(1)
    assert widget.streaming_timer.isActive()
    mmcore.stopSequenceAcquisition()
    assert not widget.streaming_timer.isActive()


seq = useq.MDASequence(
    channels=["FITC"], time_plan=useq.TIntervalLoops(interval=0.1, loops=2)
)


def test_image_preview_update_while_running_mda(qtbot: "QtBot"):
    widget = ImagePreview()
    qtbot.addWidget(widget)
    mmc = widget._mmc

    assert widget.image is None
    assert widget.use_with_mda

    with qtbot.waitSignal(mmc.mda.events.sequenceFinished):
        mmc.run_mda(seq)
    assert widget.image is not None


def test_image_preview_no_update_while_running_mda(qtbot: "QtBot"):
    widget = ImagePreview()
    qtbot.addWidget(widget)
    mmc = widget._mmc

    widget.use_with_mda = False

    assert widget.image is None
    assert not widget.use_with_mda

    with qtbot.waitSignal(mmc.mda.events.sequenceFinished):
        mmc.run_mda(seq)
    assert widget.image is None
