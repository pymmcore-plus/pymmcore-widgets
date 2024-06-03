from pathlib import Path

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.hcs._calibration_widget import (
    CalibrationData,
    PlateCalibrationWidget,
)
from pymmcore_widgets.hcs._plate_model import load_database

database_path = (
    Path(__file__).parent.parent.parent / "tests" / "plate_database_for_tests.json"
)
database = load_database(database_path)


app = QApplication([])

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()

cb = PlateCalibrationWidget(mmcore=mmc)

cb.setValue(
    CalibrationData(
        plate=database["coverslip 22mm"],
        calibration_positions_a1=[(-100, 100), (100, -100)],
    )
)
cb.show()

app.exec_()
