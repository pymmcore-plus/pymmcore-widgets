from pathlib import Path

try:
    from rich import print as rich_print
except ImportError:
    rich_print = print

from qtpy.QtWidgets import QApplication

from pymmcore_widgets.hcs._plate_database_widget import PlateDatabaseWidget

database_path = (
    Path(__file__).parent.parent.parent / "tests" / "plate_database_for_tests.json"
)

app = QApplication([])

db = PlateDatabaseWidget(plate_database_path=database_path)

db.valueChanged.connect(lambda: rich_print(db.value()))

db.show()

app.exec_()
