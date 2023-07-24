"""Functions and utils for managing the global mmcore singleton."""
from __future__ import annotations

from pymmcore_plus import CMMCorePlus


def load_system_config(config: str = "", mmcore: CMMCorePlus | None = None) -> None:
    """Internal convenience for `loadSystemConfiguration(config)`.

    This also unloads all devices first and resets the STATE.
    If config is `None` or empty string, will load the MMConfig_demo.
    Note that it should also always be fine for the end-user to use something like
    `CMMCorePlus.instance().loadSystemConfiguration(...)` (instead of this function)
    and we need to handle that as well.  So this function shouldn't get too complex.
    """
    mmc = mmcore or CMMCorePlus.instance()
    mmc.unloadAllDevices()
    mmc.loadSystemConfiguration(config or "MMConfig_demo.cfg")
