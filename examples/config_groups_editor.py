from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.config_presets._views._config_groups_editor import (
    ConfigGroupsEditor,
)

app = QApplication([])
core = CMMCorePlus()
core.loadSystemConfiguration()

cfg = ConfigGroupsEditor.create_from_core(core)
cfg.setCurrentPreset("Channel", "FITC")
cfg.show()
cfg.resize(1200, 800)

app.exec()
