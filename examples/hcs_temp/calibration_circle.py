from contextlib import suppress

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication
from useq import WellPlate

from pymmcore_widgets.hcs._calibration_widget._calibration_widget import (
    CalibrationData,
    PlateCalibrationWidget,
)

with suppress(ImportError):
    from rich import print


plate = WellPlate(rows=8, columns=12, well_spacing=(9, 9), well_size=(6.4, 6.4))

app = QApplication([])

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()

cb = PlateCalibrationWidget(mmcore=mmc)

cb.setValue(
    CalibrationData(
        plate=plate,
        calibration_positions_a1=[(-10, 0), (0, 10), (10, 0)],
        calibration_positions_an=[(90, 0), (100, 10), (110, 0)],
    )
)
cb._calibration_mode._mode_combo.setCurrentIndex(1)

cb.valueChanged.connect(print)

cb.show()

app.exec()
