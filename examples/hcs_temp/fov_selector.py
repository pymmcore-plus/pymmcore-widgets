from pathlib import Path

try:
    from rich import print as rich_print
except ImportError:
    rich_print = print

from qtpy.QtWidgets import QApplication

from pymmcore_widgets.hcs._fov_widget import Center, FOVSelectorWidget
from pymmcore_widgets.hcs._plate_model import load_database

database_path = (
    Path(__file__).parent.parent.parent / "tests" / "plate_database_for_tests.json"
)
database = load_database(database_path)


app = QApplication([])

fs = FOVSelectorWidget(
    plate=database["standard 96 wp"],
    mode=Center(x=0, y=0, fov_width=512, fov_height=512),
)

fs.valueChanged.connect(lambda x: rich_print(x))

fs.show()

app.exec_()
