import numpy as np
from pymmcore_plus import CMMCorePlus
from useq import MDAEvent, MDASequence

from pymmcore_widgets._mda._datastore import QLocalDataStore

sequence = MDASequence(
    channels=[{"config": "DAPI", "exposure": 10}],
    time_plan={"interval": 0.3, "loops": 3},
)


def test_reception(qtbot):
    mmcore = CMMCorePlus.instance()

    datastore = QLocalDataStore(
        shape=[3, 1, 1, 512, 512], dtype=np.uint16, mmcore=mmcore
    )

    with qtbot.waitSignal(datastore.frame_ready, timeout=5000):
        mmcore.run_mda(sequence, block=False)
    with qtbot.waitSignal(datastore.frame_ready, timeout=5000):
        pass

    assert datastore.get_frame([0, 0, 0]).flatten()[0] != 0
    qtbot.wait(1000)


def test_index_completion():
    mmcore = CMMCorePlus.instance()
    datastore = QLocalDataStore(
        shape=[10, 1, 1, 512, 512], dtype=np.uint16, mmcore=mmcore
    )
    min_indices = {"t": 0, "c": 0, "z": 0}
    compl_indices = datastore.complement_indices(MDAEvent(index={"t": 0, "c": 0}))
    assert min_indices == compl_indices


def test_shape_correction():
    mmcore = CMMCorePlus.instance()

    datastore = QLocalDataStore(
        shape=[3, 1, 1, 512, 512], dtype=np.uint16, mmcore=mmcore
    )
    index = {"t": 3, "c": 0, "z": 0}
    datastore.correct_shape(index)
    # time domain should double, think about if this makes actually sense...
    assert datastore.array.shape == (6, 1, 1, 512, 512)

    datastore = QLocalDataStore(
        shape=[3, 1, 1, 512, 512], dtype=np.uint16, mmcore=mmcore
    )
    index = {"t": 1, "c": 1, "z": 0}
    datastore.correct_shape(index)
    assert datastore.array.shape == (3, 1, 2, 512, 512)

    datastore = QLocalDataStore(
        shape=[3, 1, 1, 512, 512], dtype=np.uint16, mmcore=mmcore
    )
    index = {"t": 2, "c": 0, "z": 5}
    datastore.correct_shape(index)
    assert datastore.array.shape == (3, 6, 1, 512, 512)

    # Compound
    datastore = QLocalDataStore(
        shape=[3, 1, 1, 512, 512], dtype=np.uint16, mmcore=mmcore
    )
    index = {"t": 4, "c": 1, "z": 5}
    datastore.correct_shape(index)
    assert datastore.array.shape == (6, 6, 2, 512, 512)
