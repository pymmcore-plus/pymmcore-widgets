from qtpy.QtWidgets import QApplication
from useq import RandomPoints

from pymmcore_widgets.useq_widgets import PointsPlanWidget

app = QApplication([])

points = RandomPoints(
    num_points=60,
    allow_overlap=False,
    fov_width=400,
    fov_height=300,
    max_width=4000,
    max_height=4000,
)

fs = PointsPlanWidget(points)
fs.show()

app.exec()
