from contextlib import suppress

with suppress(ImportError):
    from rich import print
import useq
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.hcs._plate_widget import PlateSelectorWidget

app = QApplication([])

plate = useq.WellPlate(rows=0, columns=8, well_spacing=6, well_size=4, name="test")
plan = useq.WellPlatePlan(
    plate=plate,
    a1_center_xy=(0, 0),
    selected_wells=slice(0, 8, 2),
)
ps = PlateSelectorWidget(plan)
ps.valueChanged.connect(print)
ps.show()

app.exec()
