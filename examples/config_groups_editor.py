import sys

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import ConfigGroupsEditor

app = QApplication([])
core = CMMCorePlus()
core.loadSystemConfiguration("tests/test_config.cfg")

with_cfg = sys.argv[1].lower() in ("1", "true") if len(sys.argv) > 1 else False
cfg = ConfigGroupsEditor.create_from_core(core, load_configs=with_cfg)


# connect to apply signal to print the changes
def _on_apply_clicked(changed, deleted, channel_group):
    print("\n\nApply clicked:")
    print(f"Changed: {[cg.name for cg in changed]}")
    print(f"Deleted: {deleted}")
    print(f"Channel group: {channel_group}")


cfg.applyRequested.connect(_on_apply_clicked)

cfg.resize(900, 550)
cfg.show()

app.exec()
