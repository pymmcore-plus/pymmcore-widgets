from typing import TYPE_CHECKING
from unittest.mock import patch

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
def test_integration_snap_and_mda_behavior(qtbot: "QtBot", seq, use_with_mda):
    """Test integrated behavior of both _on_image_snapped and _on_frame_ready."""
    mmcore = CMMCorePlus.instance()
    widget = ImagePreview(use_with_mda=use_with_mda)
    qtbot.addWidget(widget)
    assert widget._mmc is mmcore
    assert mmcore.mda.engine is not None
    assert mmcore.mda.engine.use_hardware_sequencing

    # Test 1: mmcore.snap() when MDA is NOT running
    with patch.object(widget, "_update_image") as mock_update:
        # Ensure MDA is not running
        assert not mmcore.mda.is_running()

        with wait_signal(qtbot, mmcore.events.imageSnapped):
            mmcore.snap()

        # _update_image should ALWAYS be called when MDA is not running,
        # regardless of use_with_mda setting or sequence type
        mock_update.assert_called_once()

    # Test 2: mmcore.snap() when MDA IS running (simulated)
    with patch.object(widget, "_update_image") as mock_update:
        with patch.object(mmcore.mda, "is_running", return_value=True):
            with wait_signal(qtbot, mmcore.events.imageSnapped):
                mmcore.snap()

            # _update_image should NEVER be called when MDA is running,
            # regardless of use_with_mda setting or sequence type
            mock_update.assert_not_called()

    # Test 3: MDA sequence behavior based on use_with_mda setting
    # Get initial image state before MDA
    with wait_signal(qtbot, mmcore.events.imageSnapped):
        mmcore.snap()
    initial_image = widget._canvas.render()
    assert widget.image is not None

    # Run the MDA sequence (actual MDA execution)
    with wait_signal(qtbot, mmcore.mda.events.sequenceFinished):
        mmcore.mda.run(seq)

    # Get final image state after MDA
    final_image = widget._canvas.render()

    # Test behavior based on use_with_mda setting during actual MDA
    if use_with_mda:
        # When use_with_mda=True, _on_frame_ready should update the image during MDA
        # The image should be different from initial (updated during MDA)
        # This applies to both sequencable and non-sequencable sequences
        assert not np.allclose(initial_image, final_image), (
            f"Image should be updated during MDA when use_with_mda=True "
            f"(seq: {seq.time_plan})"
        )
    else:
        # When use_with_mda=False, _on_frame_ready should NOT update the image
        # during MDA. The image should remain the same as initial snap
        # This applies to both sequencable and non-sequencable sequences
        assert np.allclose(initial_image, final_image), (
            f"Image should NOT be updated during MDA when use_with_mda=False "
            f"(seq: {seq.time_plan})"
        )

    assert widget.use_with_mda is use_with_mda
