from pymmcore_plus import CMMCorePlus
from useq import MDASequence

from pymmcore_widgets._mda._datastore import QLocalDataStore
from pymmcore_widgets._mda._stack_viewer import StackViewer

sequence = MDASequence(
    channels=[{"config": "DAPI", "exposure": 10}, {"config": "FITC", "exposure": 10}],
    time_plan={"interval": 0.5, "loops": 3},
    axis_order="tpcz",
)


def test_local(qtbot):
    mmcore = CMMCorePlus.instance()
    mmcore.loadSystemConfiguration()
    datastore = QLocalDataStore(shape=(3, 1, 2, 512, 512), mmcore=mmcore)
    canvas = StackViewer(mmcore=mmcore, datastore=datastore)
    canvas.show()
    qtbot.addWidget(canvas)
    mmcore.run_mda(sequence)
    if qtbot:
        with qtbot.waitSignal(datastore.frame_ready, timeout=5000):
            pass
        with qtbot.waitSignal(datastore.frame_ready, timeout=5000):
            pass
    assert canvas.images[0]._data.shape == (512, 512)
    assert canvas.images[0]._data.flatten()[0] != 0
    assert canvas.images[1]._data.shape == (512, 512)
    assert len(canvas.channel_row.boxes) == 5
    assert len(canvas.sliders) > 1

    # qtbot.wait(1000)

    # qtbot.mouseMove(canvas, QtCore.QPoint(500, 500))
    # qtbot.wait(500)
    # qtbot.mouseMove(canvas, QtCore.QPoint(200, 200))
    # qtbot.wait(1000)
    # assert canvas.info_bar.text() != ""
