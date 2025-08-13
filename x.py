import useq
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import MDAWidget

app = QApplication([])

poly = useq.GridFromPolygon(
    vertices=[(-400, 0), (1500, -500), (500, 1900), (0, 100)],
    # vertices=[(0, 0), (300, 0), (300, 100), (100, 100), (100, 300), (0, 300)],
    fov_height=100,
    fov_width=100,
    overlap=(10, 10),
    # convex_hull=True
)
pos = useq.AbsolutePosition(x=1, y=2, z=3, sequence=useq.MDASequence(grid_plan=poly))
# seq = useq.MDASequence(grid_plan=poly, stage_positions=[pos])
seq = useq.MDASequence(grid_plan=poly)

m = MDAWidget()
m.setValue(seq)
m.show()

app.exec()
