from contextlib import suppress

with suppress(ImportError):
    pass

from qtpy.QtWidgets import QApplication
from useq import WellPlate

from pymmcore_widgets.hcs._fov_widget._fov_widget import FOVSelectorWidget

app = QApplication([])

plate = WellPlate(rows=8, columns=12, well_spacing=(9, 9), well_size=(6.4, 6.4))
fs = FOVSelectorWidget()

fs.valueChanged.connect(print)

fs.show()

app.exec()
