from contextlib import suppress

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

with suppress(ImportError):
    from rich import print

from useq import GridRowsColumns, WellPlate, WellPlatePlan

from pymmcore_widgets.hcs import HCSWizard

app = QApplication([])
mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()
w = HCSWizard()

fov_width = mmc.getImageWidth() * mmc.getPixelSizeUm()
fov_height = mmc.getImageHeight() * mmc.getPixelSizeUm()

plate = WellPlate(
    rows=8, columns=12, well_spacing=(9, 9), well_size=(6.4, 6.4), name="96-well"
)
wpp = WellPlatePlan(
    plate=plate,
    a1_center_xy=(0, 0),
    rotation=5,
    selected_wells=([1, 2, 4], [3, 4, 7]),
    well_points_plan=GridRowsColumns(
        rows=3, columns=3, fov_width=fov_width, fov_height=fov_height
    ),
)
w.setValue(wpp)

w.valueChanged.connect(print)


# override the accept method to show the plot
def _accept():
    print(w.value().plot())


w.accept = _accept

w.show()
app.exec()
