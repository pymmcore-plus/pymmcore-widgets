from contextlib import suppress

import useq
from qtpy.QtWidgets import QApplication

from useq_widgets import WellPlateWidget

with suppress(ImportError):
    from rich import print


app = QApplication([])

plan = useq.WellPlatePlan(
    plate="24-well", a1_center_xy=(0, 0), selected_wells=slice(0, 8, 2)
)

ps = WellPlateWidget(plan)
ps.valueChanged.connect(print)
ps.show()

app.exec()
