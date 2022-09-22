from typing import TYPE_CHECKING
import numpy as np

from pymmcore_widgets import ImagePreview

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot
    from pymmcore_plus import CMMCorePlus


def test_exposure_widget(qtbot: "QtBot", global_mmcore: "CMMCorePlus"):
    """Test that the exposure widget works."""
    from vispy import scene

    widget = ImagePreview()
    assert widget._mmc is global_mmcore

    qtbot.addWidget(widget)
    widget.show()

    assert isinstance(widget._canvas, scene.SceneCanvas)

    global_mmcore.snap()  # would be nice if this could be snapImage()
    img = widget._canvas.render()

    global_mmcore.snap()
    img2 = widget._canvas.render()

    assert not np.allclose(img, img2)
