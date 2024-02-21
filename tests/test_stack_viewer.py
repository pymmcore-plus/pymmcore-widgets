import pytest
from pymmcore_plus import CMMCorePlus
from qtpy import QtCore
from superqt.cmap._cmap_utils import try_cast_colormap
from useq import MDAEvent, MDASequence
from vispy.app.canvas import MouseEvent
from vispy.scene.events import SceneMouseEvent

from pymmcore_widgets._stack_viewer import CMAPS
from pymmcore_widgets.experimental import StackViewer

sequence = MDASequence(
    channels=[{"config": "DAPI", "exposure": 10}, {"config": "FITC", "exposure": 10}],
    time_plan={"interval": 0.2, "loops": 3},
    grid_plan={"rows": 2, "columns": 2, "fov_height": 512, "fov_width": 512},
    axis_order="tpcz",
)


def test_acquisition(qtbot):
    mmcore = CMMCorePlus.instance()
    canvas = StackViewer(mmcore=mmcore)
    qtbot.addWidget(canvas)

    with qtbot.waitSignal(mmcore.mda.events.sequenceFinished):
        mmcore.mda.run(sequence)
    assert canvas.images[0][0]._data.flatten()[0] != 0
    assert canvas.images[1][0]._data.shape == (512, 512)
    assert len(canvas.channel_row.boxes) == sequence.sizes.get("c", 1)
    assert len(canvas.sliders) > 1
    # canvas.close()
    # canvas.deleteLater()



def test_init_with_sequence(qtbot):
    mmcore = CMMCorePlus.instance()

    canvas = StackViewer(sequence=sequence, mmcore=mmcore)
    qtbot.addWidget(canvas)

    with qtbot.waitSignal(mmcore.mda.events.sequenceFinished):
        mmcore.mda.run(sequence)
    assert canvas.images[0][0]._data.flatten()[0] != 0
    assert canvas.images[1][0]._data.shape == (512, 512)
    # Now only the necessary sliders/boxes should have been initialized
    assert len(canvas.channel_row.boxes) == sequence.sizes.get("c", 1)
    assert len(canvas.sliders) == 1


def test_interaction(qtbot):
    mmcore = CMMCorePlus.instance()
    canvas = StackViewer(mmcore=mmcore, sequence=sequence, transform=(90, False, False))
    canvas.on_display_timer()
    canvas.show()
    qtbot.addWidget(canvas)
    with qtbot.waitSignal(mmcore.mda.events.sequenceFinished):
        mmcore.mda.run(sequence)
    # canvas.view_rect = ((0, 0), (512, 512))
    canvas.resize(700, 700)
    canvas._collapse_view()
    canvas._canvas.update()

    event = SceneMouseEvent(MouseEvent("mouse_move"), None)
    event._pos = [100, 100]
    canvas.on_mouse_move(event)
    # There should be a number there as this is on the image
    assert canvas.info_bar.text()[-1] != "]"

    # outside canvas
    event._pos = [-10, 100]
    canvas.on_mouse_move(event)
    assert canvas.info_bar.text()[-1] == "]"

    # outside image
    event._pos = [1000, 100]
    canvas.on_mouse_move(event)
    assert canvas.info_bar.text()[-1] == "]"

    canvas.sliders[0].setValue(1)
    canvas.sliders[0].lock_btn.setChecked(True)
    event = MDAEvent(index={"t": 0, "c": 0, "g": 0})
    canvas.frameReady(event)
    assert canvas.sliders[0].value() == 1

    canvas.on_clim_timer()
    color_selected = 2
    canvas.channel_row.boxes[0].color_choice.setCurrentIndex(color_selected)
    assert (
        canvas.images[0][0].cmap.colors[-1].RGB
        == try_cast_colormap(CMAPS[color_selected]).to_vispy().colors[-1].RGB
    ).all

    canvas.channel_row.boxes[0].autoscale_chbx.setChecked(False)
    canvas.channel_row.boxes[0].slider.setValue((0, 255))
    canvas.channel_row.boxes[0].show_channel.setChecked(False)
    # should be current channel
    canvas.current_channel = 1
    canvas.channel_row.boxes[1].show_channel.setChecked(False)
    canvas._canvas.update()
    # Should have been set as all channels are deselected now
    assert canvas.channel_row.boxes[0].show_channel.isChecked()

    canvas.on_display_timer()


def test_sequence_no_channels(qtbot):
    mmcore = CMMCorePlus.instance()
    canvas = StackViewer(mmcore=mmcore)
    qtbot.addWidget(canvas)
    sequence = MDASequence(time_plan={"interval": 0.5, "loops": 3})
    with qtbot.waitSignal(mmcore.mda.events.sequenceFinished):
        mmcore.mda.run(sequence)


def test_connection_warning():
    with pytest.warns(UserWarning):
        canvas = StackViewer()
    canvas.close()


def test_settings_on_close():
    mmcore = CMMCorePlus.instance()
    canvas = StackViewer(mmcore=mmcore)
    name = canvas.__class__.__name__
    canvas.move(QtCore.QPoint(50, 50))
    canvas.move(QtCore.QPoint(100, 100))
    canvas.close()
    settings = QtCore.QSettings("pymmcore_plus", name)
    assert settings.value("pos") == QtCore.QPoint(100, 100)


def test_canvas_size():
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


def test_disconnect(qtbot):
    mmcore = CMMCorePlus.instance()
    canvas = StackViewer(mmcore=mmcore)
    qtbot.addWidget(canvas)
    canvas._disconnect()
    sequence = MDASequence(time_plan={"interval": 0.5, "loops": 3})
    with qtbot.waitSignal(mmcore.mda.events.sequenceFinished):
        mmcore.mda.run(sequence)
    assert canvas.sequence is None
    assert not canvas.ready


def test_not_ready(qtbot):
    mmcore = CMMCorePlus.instance()
    canvas = StackViewer(mmcore=mmcore)
    qtbot.addWidget(canvas)
    sequence = MDASequence(time_plan={"interval": 0.5, "loops": 3})
    # TODO: we should do something here that checks if the loop finishes
    canvas.frameReady(MDAEvent())
    with qtbot.waitSignal(mmcore.mda.events.sequenceFinished):
        mmcore.mda.run(sequence)
