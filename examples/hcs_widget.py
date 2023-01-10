from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from useq import MDAEvent, MDASequence

from pymmcore_widgets import HCSWidget


class HCS(QWidget):
    """An example of using the HCS Widget.

    It can be used to create and run a useq.MDASequence for the acquisition
    of multi-well plate or custom defined areas.

    The `HCSWidget` provides a GUI to construct a `useq.MDASequence` object.
    This object describes a full multi-dimensional acquisition.

    When the `run` button is pressed, a `useq.MDASequence` is first built depending
    on the GUI values and is then passed to the `CMMCorePlus.run_mda` to actually
    execute the acquisition.

    For details of the corresponding schema and methods, see
    https://github.com/pymmcore-plus/useq-schema and
    https://github.com/pymmcore-plus/pymmcore-plus.

    In this example, we've also connected callbacks to the CMMCorePlus object's `mda`
    events to print out the current state of the acquisition.
    """

    def __init__(self) -> None:
        super().__init__()

        # get the CMMCore instance and load the default config
        self.mmc = CMMCorePlus.instance()
        self.mmc.loadSystemConfiguration()

        # connect MDA acquisition events to local callbacks
        # in this example we're just printing the current state of the acquisition
        self.mmc.mda.events.sequenceStarted.connect(self._on_start)
        self.mmc.mda.events.frameReady.connect(self._on_frame)
        self.mmc.mda.events.sequenceFinished.connect(self._on_end)
        self.mmc.mda.events.sequencePauseToggled.connect(self._on_pause)

        # instantiate the MultiDWidget, and a couple lables for feedback
        self.hcs = HCSWidget()
        self.current_sequence = QLabel('... enter info and click "Run"')
        self.current_event = QLabel("... current event info will appear here")

        # below here is just GUI layout stuff
        hcs_wdg = QGroupBox()
        hcs_wdg.setMinimumWidth(650)
        hcs_wdg.setLayout(QVBoxLayout())
        hcs_wdg.layout().setContentsMargins(0, 0, 0, 0)
        hcs_wdg.layout().addWidget(self.hcs)

        _scroll = QScrollArea()
        _scroll.setWidgetResizable(True)
        _scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_wdg = QGroupBox()
        lbl_wdg.setMinimumWidth(275)
        lbl_wdg.setLayout(QVBoxLayout())
        lbl_wdg.layout().addWidget(QLabel(text="<h3>ACQUISITION SEQUENCE</h3>"))
        lbl_wdg.layout().addWidget(self.current_sequence)
        lbl_wdg.layout().addWidget(QLabel(text="<h3>ACQUISITION EVENT</h3>"))
        lbl_wdg.layout().addWidget(self.current_event)

        _scroll.setWidget(lbl_wdg)

        self.setLayout(QHBoxLayout())
        self.layout().addWidget(hcs_wdg)
        self.layout().addWidget(_scroll)
        self.resize(900, 800)

    def _on_start(self, sequence: MDASequence) -> None:
        """Called when the MDA sequence starts."""
        self.current_sequence.setText(sequence.yaml())

    def _on_frame(self, image, event: MDAEvent) -> None:
        """Called each time a frame is acquired."""
        self.current_event.setText(
            f"index: {event.index}\n"
            f"channel: {event.channel.config}\n"
            f"exposure: {event.exposure}\n"
            f"pos_name: {event.pos_name}\n"
            f"xyz: ({event.x_pos}, {event.y_pos}, {event.z_pos})\n"
        )

    def _on_end(self) -> None:
        """Called when the MDA sequence ends."""
        self.current_event.setText("Finished!")

    def _on_pause(self, state: bool) -> None:
        """Called when the MDA is paused."""
        txt = "Paused..." if state else "Resumed!"
        self.current_event.setText(txt)


if __name__ == "__main__":
    app = QApplication([])
    frame = HCS()
    frame.show()
    app.exec_()
