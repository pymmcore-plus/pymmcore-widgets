from contextlib import suppress

with suppress(ImportError):
    from rich import print
import useq
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.useq_widgets import WellPlateWidget

app = QApplication([])

plan = useq.WellPlatePlan(
    plate=useq.WellPlate(rows=8, columns=8, well_spacing=6, well_size=4, name="test"),
    a1_center_xy=(0, 0),
    rotation=5,
    selected_wells=slice(0, 8, 2),
)

ps = WellPlateWidget(plan)
ps.valueChanged.connect(print)
ps.show()

app.exec()
