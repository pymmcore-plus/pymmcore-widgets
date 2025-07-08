from pymmcore_plus import CMMCorePlus

from pymmcore_widgets._models import (
    get_available_devices,
    get_config_groups,
    get_loaded_devices,
)


def test_get_loaded_devices() -> None:
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    get_loaded_devices(core)
    get_available_devices(core)
    get_config_groups(core)
