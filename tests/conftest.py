from pathlib import Path

import pytest
from pymmcore_plus import CMMCorePlus
from pytestqt.qtbot import QtBot

from pymmcore_widgets._pixel_size_widget import PixelSizeWidget


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
def px_wdg(global_mmcore, qtbot: QtBot):
    px_size_wdg = PixelSizeWidget(mmcore=global_mmcore)
    table = px_size_wdg.table
    obj = px_size_wdg.objective_device
    qtbot.addWidget(px_size_wdg)
    mmc = global_mmcore
    return px_size_wdg, table, obj, mmc
