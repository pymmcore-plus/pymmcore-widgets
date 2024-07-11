from qtpy.QtWidgets import QApplication
from useq import RandomPoints

from pymmcore_widgets.useq_widgets import PointsPlanWidget

app = QApplication([])

points = RandomPoints(
    num_points=60,
    allow_overlap=False,
    fov_width=300,
    fov_height=200,
    max_width=4000,
    max_height=4000,
)

fs = PointsPlanWidget()
# fs.setWellSize(6, 6)
fs.show()

app.exec()
