from pathlib import Path

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

try:
    from rich import print as rich_print
except ImportError:
    rich_print = print

from pymmcore_widgets.hcs import HCSWizard
from pymmcore_widgets.hcs._calibration_widget import CalibrationData
from pymmcore_widgets.hcs._fov_widget import Center
from pymmcore_widgets.hcs._graphics_items import Well
from pymmcore_widgets.hcs._main_wizard_widget import HCSData
from pymmcore_widgets.hcs._plate_model import load_database

database_path = Path(__file__).parent.parent / "tests" / "plate_database_for_tests.json"
database = load_database(database_path)


app = QApplication([])
mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()
w = HCSWizard()

width = mmc.getImageWidth() * mmc.getPixelSizeUm()
height = mmc.getImageHeight() * mmc.getPixelSizeUm()

data = HCSData(
    plate=database["standard 96 wp"],
    wells=[Well("A1", 0, 0), Well("B2", 1, 1), Well("C3", 2, 2)],
    mode=Center(x=0, y=0, fov_width=width, fov_height=height),
    calibration=CalibrationData(
        plate=database["standard 96 wp"],
        calibration_positions_a1=[(-10, 0), (0, 10), (10, 0)],
        calibration_positions_an=[(90, 0), (100, 10), (110, 0)],
    ),
)
w.setValue(data)

w.valueChanged.connect(lambda: rich_print(w.value()))

w.show()
app.exec_()
