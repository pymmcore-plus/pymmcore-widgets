from pathlib import Path

from pymmcore_plus import CMMCorePlus

try:
    from rich import print as rich_print
except ImportError:
    rich_print = print

from pymmcore_widgets.hcs import HCSWizard
from pymmcore_widgets.hcs._calibration_widget._calibration_widget import CalibrationData

# from pymmcore_widgets.hcs._calibration_widget import CalibrationData
# from pymmcore_widgets.hcs._fov_widget import Center
# from pymmcore_widgets.hcs._main_wizard_widget import HCSData
from pymmcore_widgets.hcs._plate_model import load_database

database_path = Path(__file__).parent.parent / "tests" / "plate_database_for_tests.json"
database = load_database(database_path)


# app = QApplication([])
mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()
w = HCSWizard()
p = w.plate_page
c = w.calibration_page
f = w.fov_page


p.combo.setCurrentText("96-well")

c.setValue(
    CalibrationData(
        plate=w._plate,
        calibration_positions_a1=[(-10, 0), (0, 10), (10, 0)],
        calibration_positions_an=[(90, 0), (100, 10), (110, 0)],
    )
)

# width = mmc.getImageWidth() * mmc.getPixelSizeUm()
# height = mmc.getImageHeight() * mmc.getPixelSizeUm()

# data = HCSData(
#     plate=database["standard 96 wp"],
#     wells=[
#         Well(name="A1", row=0, column=0),
#         Well(name="B2", row=1, column=1),
#         Well(name="C3", row=2, column=2),
#     ],
#     mode=Center(x=0, y=0, fov_width=width, fov_height=height),
#     calibration=CalibrationData(
#         plate=database["standard 96 wp"],
#         calibration_positions_a1=[(-10, 0), (0, 10), (10, 0)],
#         calibration_positions_an=[(90, 0), (100, 10), (110, 0)],
#     ),
# )
# w.setValue(data)

w.valueChanged.connect(lambda: rich_print(w.value()))

w.show()
# app.exec()
