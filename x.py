import useq
from qtpy.QtWidgets import QApplication

from pymmcore_widgets import MDAWidget

app = QApplication([])

poly = useq.GridFromPolygon(
    # vertices=[(0, 0), (10, -5), (12, 15), (0, 8)],
    vertices=[(-4, 0), (5, -5), (5, 9), (0, 10)],
    fov_height=1,
    fov_width=1,
    overlap=(0.1, 0.1)
)
pos = useq.AbsolutePosition(
    x=1, y=2, z=3, sequence=useq.MDASequence(grid_plan=poly))
seq = useq.MDASequence(grid_plan=poly, stage_positions=[pos])

m = MDAWidget()
m.setValue(seq)
m.show()

app.exec()
