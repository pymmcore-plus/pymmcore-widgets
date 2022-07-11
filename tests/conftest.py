from pathlib import Path

import pytest
from pymmcore_plus import CMMCorePlus

from pymmcore_widgets import _core


@pytest.fixture(params=["local"])
def global_mmcore(request):
    _core._SESSION_CORE = CMMCorePlus()  # refresh singleton
    if request.param == "remote":
        from pymmcore_plus import server

        server.try_kill_server()

    mmc = _core.get_core_singleton(remote=request.param == "remote")
    if len(mmc.getLoadedDevices()) < 2:
        mmc.loadSystemConfiguration(str(Path(__file__).parent / "test_config.cfg"))
    return mmc
