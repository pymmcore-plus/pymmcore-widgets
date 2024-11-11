from pymmcore_plus import CMMCorePlus
from useq import MDAEvent, MDASequence

from pymmcore_widgets.views._stack_viewer._datastore import QOMEZarrDatastore

sequence = MDASequence(
    channels=[{"config": "DAPI", "exposure": 10}],
    time_plan={"interval": 0.3, "loops": 3},
)


def test_reception(qtbot):
    mmcore = CMMCorePlus.instance()

    datastore = QOMEZarrDatastore()
    mmcore.mda.events.frameReady.connect(datastore.frameReady)
    mmcore.mda.events.sequenceFinished.connect(datastore.sequenceFinished)
    mmcore.mda.events.sequenceStarted.connect(datastore.sequenceStarted)

    with qtbot.waitSignal(datastore.frame_ready, timeout=5000):
        mmcore.run_mda(sequence, block=False)
    with qtbot.waitSignal(datastore.frame_ready, timeout=5000):
        pass

    assert datastore.get_frame(MDAEvent(index={"c": 0, "t": 0})).flatten()[0] != 0
    qtbot.wait(1000)
