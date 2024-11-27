from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets import StageWidget
from pymmcore_widgets.control import StageExplorer


class Explorer(QWidget):
    """Example that shows the use of the `StageExplorer` widget."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stage Explorer")

        stage = StageWidget("XY")
        stage.setStep(512)
        stage.snap_checkbox.setChecked(True)
        stage_layout = QVBoxLayout()
        stage_layout.addWidget(stage)
        stage_layout.addStretch()

        stage_explorer = StageExplorer()
        stage_explorer.poll_stage_position = True

        layout = QHBoxLayout(self)
        layout.addLayout(stage_layout)
        layout.addWidget(stage_explorer)


if __name__ == "__main__":
    app = QApplication([])
    mmc = CMMCorePlus.instance()
    mmc.loadSystemConfiguration()
    window = Explorer()
    window.show()
    app.exec()
