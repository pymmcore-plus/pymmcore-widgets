from typing import TYPE_CHECKING

import numpy as np
from pymmcore_plus import CMMCorePlus

from pymmcore_widgets import ImagePreview

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_image_preview(qtbot: "QtBot"):
    """Test that the exposure widget works."""
    from vispy import scene

    mmcore = CMMCorePlus.instance()
    widget = ImagePreview()
    assert widget._mmc is mmcore

    widget.show()

    assert isinstance(widget._canvas, scene.SceneCanvas)

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

    with qtbot.waitSignal(widget.destroyed):
        widget.close()
        widget.deleteLater()
