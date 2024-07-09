from contextlib import suppress

with suppress(ImportError):
    from rich import print

from qtpy.QtWidgets import QApplication

from pymmcore_widgets.hcs._plate_widget import PlateSelectorWidget

app = QApplication([])

ps = PlateSelectorWidget()
ps.valueChanged.connect(print)
ps.show()

app.exec()
