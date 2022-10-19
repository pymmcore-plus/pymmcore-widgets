import numpy as np
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from useq import MDAEvent, MDASequence

from pymmcore_widgets import MultiDWidget


class MDA(QWidget):
    """
    An example widget for the MultiDWidget acquisition widget.

    The MultiDWidget can beused to build a mda experiment.
    The 'Run' button is linked to the pymmcore-plus 'run_mda' method.

    In this example, the whole acquisition sequence as well as each acquisition event
    are dysplayed in two QLabel widgets.
    """

    def __init__(self) -> None:
        super().__init__()

        self.setMaximumWidth(800)

        mmc = CMMCorePlus.instance()
        mmc.loadSystemConfiguration()

        mmc.mda.events.sequenceStarted.connect(self._on_start)
        mmc.mda.events.frameReady.connect(self._on_event)
        mmc.mda.events.sequenceFinished.connect(self._on_end)
        mmc.mda.events.sequencePauseToggled.connect(self._on_pause)

        mda_wdg = QGroupBox()
        mda_wdg.setMaximumWidth(500)
        mda_wdg.setLayout(QVBoxLayout())
        self.mda = MultiDWidget()
        mda_wdg.layout().addWidget(self.mda)

        lbl_wdg = QGroupBox()
        lbl_wdg.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        lbl_wdg.setLayout(QVBoxLayout())
        self.lbl_sequence = QLabel(text="\nACQUISITION SEQUENCE:")
        self.lbl_event = QLabel(text="ACQUISITION EVENT:")
        lbl_wdg.layout().addWidget(self.lbl_sequence)
        lbl_wdg.layout().addWidget(self.lbl_event)

        self.setLayout(QHBoxLayout())
        self.layout().addWidget(mda_wdg)
        self.layout().addWidget(lbl_wdg)

    def _on_start(self, sequence: MDASequence) -> None:
        self.lbl_sequence.clear()
        self.lbl_event.clear()
        self.lbl_sequence.setText(f"\nACQUISITION SEQUENCE:\n\n{sequence.yaml()}")

    def _on_event(self, image: np.ndarray, event: MDAEvent) -> None:
        self.lbl_event.clear()
        self.lbl_event.setText(
            "ACQUISITION EVENT:\n\n"
            f"index: {event.index}\n"
            f"channel: {event.channel.config}\n"
            f"exposure: {event.exposure}\n"
            f"pos_name: {event.pos_name}\n"
            f"xyz: ({event.x_pos}, {event.y_pos}, {event.z_pos})\n"
        )

    def _on_end(self) -> None:
        self.lbl_event.clear()
        self.lbl_event.setText("ACQUISITION FINISHED.")

    def _on_pause(self, state: bool) -> None:
        self.lbl_event.clear()
        if state:
            self.lbl_event.setText("ACQUISITION EVENT:\n\n" "acquisition paused...")
        else:
            self.lbl_event.setText("ACQUISITION EVENT:\n\n" "restarting acquisition...")


if __name__ == "__main__":
    app = QApplication([])
    frame = MDA()
    frame.show()
    app.exec_()
