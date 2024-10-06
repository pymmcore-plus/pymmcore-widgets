from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
import qtpy
from pymmcore_plus import CMMCorePlus
from qtpy import QtCore
from superqt.cmap._cmap_utils import try_cast_colormap
from useq import MDAEvent, MDASequence
from vispy.app.canvas import MouseEvent
from vispy.scene.events import SceneMouseEvent

from pymmcore_widgets.experimental import StackViewer
from pymmcore_widgets.views._stack_viewer import CMAPS

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


sequence = MDASequence(
    channels=[{"config": "DAPI", "exposure": 10}, {"config": "FITC", "exposure": 10}],
    time_plan={"interval": 0.2, "loops": 3},
    grid_plan={"rows": 2, "columns": 2, "fov_height": 512, "fov_width": 512},
    axis_order="tpcz",
)


def test_acquisition(qtbot: QtBot) -> None:
    mmcore = CMMCorePlus.instance()
    canvas = StackViewer(mmcore=mmcore)
    qtbot.addWidget(canvas)

    mmcore.mda.run(sequence)
    qtbot.wait(10)
    assert canvas.images[(("c", 0), ("g", 0))]._data.flatten()[0] != 0
    assert canvas.images[(("c", 1), ("g", 0))]._data.shape == (512, 512)
    assert len(canvas.channel_row.boxes) == sequence.sizes.get("c", 1)
    assert len(canvas.sliders) > 0


def test_init_with_sequence(qtbot: QtBot) -> None:
    mmcore = CMMCorePlus.instance()

    canvas = StackViewer(sequence=sequence, mmcore=mmcore)
    qtbot.addWidget(canvas)

    mmcore.mda.run(sequence)
    qtbot.wait(10)

    assert canvas.images[(("c", 0), ("g", 0))]._data.flatten()[0] != 0
    assert canvas.images[(("c", 1), ("g", 0))]._data.shape == (512, 512)
    # Now only the necessary sliders/boxes should have been initialized
    assert len(canvas.channel_row.boxes) == sequence.sizes.get("c", 1)
    assert len(canvas.sliders) == 1


@pytest.mark.skip(reason="Fails too often on CI. Usually (but not only) PySide6")
def test_interaction(qtbot: QtBot) -> None:
    mmcore = CMMCorePlus.instance()
    viewer = StackViewer(mmcore=mmcore, sequence=sequence, transform=(90, False, False))
    qtbot.addWidget(viewer)
    viewer.show()
    mmcore.mda.run(sequence)  # this is blocking

    # canvas.view_rect = ((0, 0), (512, 512))
    viewer.resize(700, 700)
    viewer._collapse_view()
    viewer._canvas.update()

    # outside canvas
    event = SceneMouseEvent(MouseEvent("mouse_move"), None)
    event._pos = [-10, 100]
    viewer.on_mouse_move(event)
    assert viewer.info_bar.text()[-1] == "]"

    # outside image
    event._pos = [1000, 100]
    viewer.on_mouse_move(event)
    assert viewer.info_bar.text()[-1] == "]"

    event._pos = [200, 200]
    viewer.on_mouse_move(event)

    # There should be a number there as this is on the image
    assert viewer.info_bar.text()[-1] != "]"

    viewer.sliders["t"].setValue(1)
    viewer.sliders["t"].lock_btn.setChecked(True)
    event = MDAEvent(index={"t": 0, "c": 0, "g": 0})
    viewer.frameReady(event)
    assert viewer.sliders["t"].value() == 1

    viewer.on_clim_timer()
    color_selected = 2
    viewer.channel_row.boxes[0].color_choice.setCurrentIndex(color_selected)
    assert (
        viewer.images[(("c", 0), ("g", 0))].cmap.colors[-1].RGB
        == try_cast_colormap(CMAPS[color_selected]).to_vispy().colors[-1].RGB
    ).all

    viewer.channel_row.boxes[0].autoscale_chbx.setChecked(False)
    viewer.channel_row.boxes[0].slider.setValue((0, 255))
    viewer.channel_row.boxes[0].show_channel.setChecked(False)
    # should be current channel
    viewer.current_channel = 1
    viewer.channel_row.boxes[1].show_channel.setChecked(False)
    viewer._canvas.update()
    # Should have been set as all channels are deselected now
    assert viewer.channel_row.boxes[0].show_channel.isChecked()


def test_sequence_no_channels(qtbot: QtBot) -> None:
    mmcore = CMMCorePlus.instance()
    canvas = StackViewer(mmcore=mmcore)
    qtbot.addWidget(canvas)
    sequence = MDASequence(time_plan={"interval": 0.5, "loops": 3})
    mmcore.mda.run(sequence)


# import gc
# gc.set_debug(gc.DEBUG_UNCOLLECTABLE)
def test_connection_warning(qtbot: QtBot) -> None:
    with pytest.warns(UserWarning, match="No datastore or mmcore provided"):
        canvas = StackViewer()
        qtbot.addWidget(canvas)


def test_settings_on_close() -> None:
    mmcore = CMMCorePlus.instance()
    canvas = StackViewer(mmcore=mmcore)
    name = canvas.__class__.__name__
    canvas.move(QtCore.QPoint(50, 50))
    canvas.move(QtCore.QPoint(100, 100))
    canvas.close()
    settings = QtCore.QSettings("pymmcore_plus", name)
    assert settings.value("pos") == QtCore.QPoint(100, 100)


def test_canvas_size() -> None:
    mmcore = CMMCorePlus.instance()
    canvas = StackViewer(mmcore=mmcore)
    canvas.img_size = (128, 128)
    canvas.view_rect = ((0, 0), (0, 0))
    event = MDAEvent()
    canvas._expand_canvas_view(event)
    assert canvas.view_rect[0][0] <= 0
    assert canvas.view_rect[0][1] <= 0
    assert canvas.view_rect[1][0] >= 128
    assert canvas.view_rect[1][1] >= 128
    events = MDASequence(
        grid_plan={"rows": 2, "columns": 2, "fov_height": 128, "fov_width": 128}
    )
    for event in events:
        canvas._expand_canvas_view(event)
    assert canvas.view_rect[0][0] <= -128
    assert canvas.view_rect[0][1] <= -128
    assert canvas.view_rect[1][0] >= 256
    assert canvas.view_rect[1][1] >= 256


def test_disconnect(qtbot: QtBot) -> None:
    mmcore = CMMCorePlus.instance()
    canvas = StackViewer(mmcore=mmcore)
    qtbot.addWidget(canvas)
    canvas._disconnect()
    sequence = MDASequence(time_plan={"interval": 0.5, "loops": 3})
    mmcore.mda.run(sequence)
    assert canvas.sequence is None
    assert not canvas.ready


@pytest.mark.skipif(
    bool(os.getenv("CI") and qtpy.API_NAME == "PySide6"), reason="Fails too often on CI"
)
def test_not_ready(qtbot: QtBot) -> None:
    mmcore = CMMCorePlus.instance()
    canvas = StackViewer(mmcore=mmcore)
    qtbot.addWidget(canvas)
    sequence = MDASequence(time_plan={"interval": 0.5, "loops": 3})
    # TODO: we should do something here that checks if the loop finishes
    canvas.frameReady(MDAEvent())
    mmcore.mda.run(sequence)
