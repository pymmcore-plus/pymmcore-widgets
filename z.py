from qtpy.QtWidgets import QApplication
from superqt import QLabeledRangeSlider

app = QApplication([])
sld = QLabeledRangeSlider()
# sld = QSlider()
sld.valueChanged.connect(lambda x: print(x))
sld.show()
app.exec_()
