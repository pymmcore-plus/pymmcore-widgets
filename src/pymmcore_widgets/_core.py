"""Functions and utils for managing the global mmcore singleton."""
from __future__ import annotations

import re
from typing import Iterator

from pymmcore_plus import CMMCorePlus

MAG_PATTERN = re.compile(r"(\d{1,3})[xX]")
RESOLUTION_ID_PREFIX = "px_size_"


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


def iter_dev_props(mmc: CMMCorePlus | None = None) -> Iterator[tuple[str, str]]:
    """Yield all pairs of currently loaded (device_label, property_name)."""
    mmc = mmc or CMMCorePlus.instance()
    for dev in mmc.getLoadedDevices():
        for prop in mmc.getDevicePropertyNames(dev):
            yield dev, prop
