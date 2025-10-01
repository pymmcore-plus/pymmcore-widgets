from typing import TYPE_CHECKING

import numpy as np
import pytest
import useq
from pymmcore_plus import CMMCorePlus

from pymmcore_widgets import ImagePreview

from ._utils import wait_signal

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_image_preview(qtbot: "QtBot"):
    """Test that the exposure widget works."""
    mmcore = CMMCorePlus.instance()
    widget = ImagePreview()
    qtbot.addWidget(widget)
    assert widget._mmc is mmcore

    with wait_signal(qtbot, mmcore.events.imageSnapped):
        mmcore.snap()
    img = widget._canvas.render()

    with wait_signal(qtbot, mmcore.events.imageSnapped):
        mmcore.snap()
    img2 = widget._canvas.render()

    assert not np.allclose(img, img2)

    assert not widget.streaming_timer.isActive()
    mmcore.startContinuousSequenceAcquisition(1)
    assert widget.streaming_timer.isActive()
    mmcore.stopSequenceAcquisition()
    assert not widget.streaming_timer.isActive()


SEQ = [
    # sequencable
    useq.MDASequence(
        time_plan=useq.TIntervalLoops(interval=0, loops=3),
        channels=(["FITC"]),
    ),
    # non-sequencable
    useq.MDASequence(
        time_plan=useq.TIntervalLoops(interval=0.2, loops=3),
        channels=(["FITC"]),
    ),
]


@pytest.mark.parametrize("seq", SEQ)
@pytest.mark.parametrize("use_with_mda", [True, False])
def test_image_preview_with_mda_sequences(
    qtbot: "QtBot", seq: useq.MDASequence, use_with_mda: bool
):
    """Test ImagePreview widget MDA frame updates based on use_with_mda setting."""
    mmcore = CMMCorePlus.instance()
    widget = ImagePreview(use_with_mda=use_with_mda)
    qtbot.addWidget(widget)
    assert widget._mmc is mmcore
    assert mmcore.mda.engine is not None
    assert mmcore.mda.engine.use_hardware_sequencing

    assert mmcore.mda.engine.use_hardware_sequencing

    # Get initial image state
    with wait_signal(qtbot, mmcore.events.imageSnapped):
        mmcore.snap()
    initial_image = widget._canvas.render()
    assert widget.image is not None

    # Run MDA sequence and wait for it to complete
    with wait_signal(qtbot, mmcore.mda.events.sequenceFinished):
        mmcore.mda.run(seq)

    # Get final image state
    final_image = widget._canvas.render()

    # Test behavior based on use_with_mda setting
    if use_with_mda:
        # When use_with_mda=True, _on_frame_ready should update the image
        # The image should be different from initial (updated during MDA)
        assert not np.allclose(initial_image, final_image), (
            "Image should be updated during MDA when use_with_mda=True"
        )
    else:
        # When use_with_mda=False, _on_frame_ready should NOT update the image
        # The image should remain the same as initial snap
        assert np.allclose(initial_image, final_image), (
            "Image should NOT be updated during MDA when use_with_mda=False"
        )

    assert widget.use_with_mda is use_with_mda
