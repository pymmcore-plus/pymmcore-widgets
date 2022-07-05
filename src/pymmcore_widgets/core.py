"""Functions and utils for managing the global mmcore singleton."""
from __future__ import annotations

import re
from typing import Iterator, Optional, Tuple

from pymmcore_plus import CMMCorePlus

MAG_PATTERN = re.compile(r"(\d{1,3})[xX]")
RESOLUTION_ID_PREFIX = "px_size_"
_SESSION_CORE: Optional[CMMCorePlus] = None


def get_core_singleton(remote: bool = False) -> CMMCorePlus:
    """Retrieve the MMCore singleton for this session.

    The first call to this function determines whether we're running remote or not.
    perhaps a temporary function for now...
    """
    global _SESSION_CORE
    if _SESSION_CORE is None:
        if remote:
            from pymmcore_plus import RemoteMMCore

            _SESSION_CORE = RemoteMMCore()
        else:
            _SESSION_CORE = CMMCorePlus.instance()
    return _SESSION_CORE


def load_system_config(config: str = "") -> None:
    """Internal convenience for `loadSystemConfiguration(config)`.

    This also unloads all devices first and resets the STATE.
    If config is `None` or empty string, will load the MMConfig_demo.
    Note that it should also always be fine for the end-user to use something like
    `CMMCorePlus.instance().loadSystemConfiguration(...)` (instead of this function)
    and we need to handle that as well.  So this function shouldn't get too complex.
    """
    mmc = get_core_singleton()
    mmc.unloadAllDevices()
    mmc.loadSystemConfiguration(config or "MMConfig_demo.cfg")


def iter_dev_props(mmc: Optional[CMMCorePlus] = None) -> Iterator[Tuple[str, str]]:
    """Yield all pairs of currently loaded (device_label, property_name)."""
    mmc = mmc or get_core_singleton()
    for dev in mmc.getLoadedDevices():
        for prop in mmc.getDevicePropertyNames(dev):
            yield dev, prop
