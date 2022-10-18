from pathlib import Path

import pytest
from pymmcore_plus import CMMCorePlus
from pytestqt.qtbot import QtBot

from pymmcore_widgets._hcs_widget._main_hcs_widget import HCSWidget


# to create a new CMMCorePlus() for every test
@pytest.fixture
def core(monkeypatch):
    new_core = CMMCorePlus()
    monkeypatch.setattr("pymmcore_plus.core._mmcore_plus._instance", new_core)
    return new_core


@pytest.fixture()
def global_mmcore(core):
    mmc = CMMCorePlus.instance()
    assert mmc == core
    mmc.loadSystemConfiguration(str(Path(__file__).parent / "test_config.cfg"))
    return mmc


@pytest.fixture()
def hcs_wdg(global_mmcore, qtbot: QtBot):
    hcs = HCSWidget(mmcore=global_mmcore)
    mmc = hcs._mmc
    cal = hcs.calibration
    qtbot.add_widget(hcs)
    with qtbot.waitSignal(hcs.wp_combo.currentTextChanged):
        hcs.wp_combo.setCurrentText("standard 6")
    return hcs, mmc, cal
