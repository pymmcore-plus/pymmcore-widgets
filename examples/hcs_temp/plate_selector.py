from contextlib import suppress

with suppress(ImportError):
    from rich import print

from qtpy.QtWidgets import QApplication

from pymmcore_widgets.hcs._plate_widget import _PlateSelectorWidget

app = QApplication([])

ps = _PlateSelectorWidget()

ps.valueChanged.connect(print)

ps.show()

app.exec()
