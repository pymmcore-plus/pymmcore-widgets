from qtpy.QtWidgets import QApplication
from useq import RandomPoints

from pymmcore_widgets.hcs._fov_widget._fov_widget import FOVSelectorWidget

app = QApplication([])

fs = FOVSelectorWidget(RandomPoints(num_points=80, allow_overlap=False))
fs.show()

app.exec()
