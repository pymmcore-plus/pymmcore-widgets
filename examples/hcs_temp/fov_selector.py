from contextlib import suppress

with suppress(ImportError):
    pass

from qtpy.QtWidgets import QApplication
from useq import RandomPoints

from pymmcore_widgets.hcs._fov_widget._fov_widget import FOVSelectorWidget

app = QApplication([])

fs = FOVSelectorWidget(RandomPoints(num_points=10))
fs.show()

app.exec()
