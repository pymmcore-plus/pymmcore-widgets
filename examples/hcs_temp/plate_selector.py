from contextlib import suppress
from pathlib import Path

with suppress(ImportError):
    from rich import print

from qtpy.QtWidgets import QApplication

from pymmcore_widgets.hcs._plate_widget import PlateSelectorWidget

database_path = (
    Path(__file__).parent.parent.parent / "tests" / "plate_database_for_tests.json"
)

app = QApplication([])

ps = PlateSelectorWidget(plate_database_path="")

ps.valueChanged.connect(print)

ps.show()

app.exec()
