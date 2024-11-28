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

        self.stage_explorer = StageExplorer()
        self.stage_explorer.poll_stage_position = True

        layout = QHBoxLayout(self)
        layout.addLayout(stage_layout)
        layout.addWidget(self.stage_explorer)

        self.stage_explorer.scaleChanged.connect(self._on_scale_changed)

    def _on_scale_changed(self, scale: int) -> None:
        print(f"Scale changed to: {scale}")


if __name__ == "__main__":
    app = QApplication([])
    mmc = CMMCorePlus.instance()
    mmc.loadSystemConfiguration()
    wdg = Explorer()
    wdg.show()
    app.exec()
