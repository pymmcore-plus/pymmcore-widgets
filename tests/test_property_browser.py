from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_widgets import PropertyBrowser

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_prop_browser(global_mmcore: CMMCorePlus, qtbot: QtBot):
    pb = PropertyBrowser(mmcore=global_mmcore)
    qtbot.addWidget(pb)
    pb.show()


def test_prop_browser_core_reset(global_mmcore: CMMCorePlus, qtbot: QtBot):
    """test that loading and resetting doesn't cause errors."""
    global_mmcore.unloadAllDevices()
    pb = PropertyBrowser(mmcore=global_mmcore)
    qtbot.addWidget(pb)
    global_mmcore.loadSystemConfiguration()
    global_mmcore.reset()
