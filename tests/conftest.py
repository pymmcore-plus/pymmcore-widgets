from pathlib import Path

import pytest
from pymmcore_plus import CMMCorePlus


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
