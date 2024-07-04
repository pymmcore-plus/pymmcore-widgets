from pathlib import Path

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

try:
    from rich import print as rich_print
except ImportError:
    rich_print = print

from useq import GridRowsColumns, WellPlatePlan

from pymmcore_widgets.hcs import HCSWizard
from pymmcore_widgets.hcs._util import load_database

database_path = Path(__file__).parent.parent / "tests" / "plate_database_for_tests.json"
database = load_database(database_path)


app = QApplication([])
mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()
w = HCSWizard()

fov_width = mmc.getImageWidth() * mmc.getPixelSizeUm()
fov_height = mmc.getImageHeight() * mmc.getPixelSizeUm()

plate = database["96-well"]
wpp = WellPlatePlan(
    plate=plate,
    a1_center_xy=(0, 0),
    rotation=5,
    selected_wells=([1, 2, 4], [3, 4, 7]),
    well_points_plan=GridRowsColumns(
        rows=3, columns=3, fov_width=fov_width, fov_height=fov_height
    ),
)
w.setValue(wpp)

w.valueChanged.connect(lambda: rich_print(w.value()))

w.show()
app.exec()
