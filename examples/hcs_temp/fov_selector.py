from contextlib import suppress

with suppress(ImportError):
    pass

from qtpy.QtWidgets import QApplication
from useq import WellPlate

from pymmcore_widgets.hcs._fov_widget._fov_sub_widgets import Center
from pymmcore_widgets.hcs._fov_widget._fov_widget import _FOVSelectorWidget

app = QApplication([])

plate = WellPlate(rows=8, columns=12, well_spacing=(9, 9), well_size=(6.4, 6.4))
fs = _FOVSelectorWidget(
    plate=plate, mode=Center(x=0, y=0, fov_width=512, fov_height=512)
)

fs.valueChanged.connect(print)

fs.show()

app.exec()
