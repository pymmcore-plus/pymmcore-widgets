import useq
from qtpy.QtWidgets import QApplication

from pymmcore_widgets.hcs._plate_test_widget import PlateTestWidget

app = QApplication([])
plate = useq.WellPlate.from_str("96-well")
w = PlateTestWidget()
w.set_plate(plate)
w.show()
app.exec()
