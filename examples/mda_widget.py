from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from useq import MDAEvent

from pymmcore_widgets import MDAWidget


class MDA(QWidget):
    """An example of using the MDAWidget to create and acquire a useq.MDASequence.

    The `MDAWidget` provides a GUI to construct a `useq.MDASequence` object.
    This object describes a full multi-dimensional acquisition;
    In this example, we set the `MDAWidget` parameter `include_run_button` to `True`,
    meaning that a `run` button is added to the GUI. When pressed, a `useq.MDASequence`
    is first built depending on the GUI values and is then passed to the
    `CMMCorePlus.run_mda` to actually execute the acquisition.
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
        self.mmc.mda.events.frameReady.connect(self._on_frame)
        self.mmc.mda.events.sequenceFinished.connect(self._on_end)
        self.mmc.mda.events.sequencePauseToggled.connect(self._on_pause)

        # instantiate the MDAWidget, and a couple labels for feedback
        self.mda = MDAWidget()
        self.mda.valueChanged.connect(self._update_sequence)
        self.current_sequence = QLabel('... enter info and click "Run"')
        self.current_event = QLabel("... current event info will appear here")

        lbl_wdg = QGroupBox()
        lbl_layout = QVBoxLayout(lbl_wdg)
        lbl_layout.addWidget(QLabel(text="<h3>ACQUISITION SEQUENCE</h3>"))
        lbl_layout.addWidget(self.current_sequence)
        lbl_layout.addWidget(QLabel(text="<h3>ACQUISITION EVENT</h3>"))
        lbl_layout.addWidget(self.current_event)

        layout = QHBoxLayout(self)
        layout.addWidget(self.mda)
        layout.addWidget(lbl_wdg)

    def _update_sequence(self) -> None:
        """Called when the MDA sequence starts."""
        self.current_sequence.setText(self.mda.value().yaml(exclude_defaults=True))

    def _on_frame(self, image, event: MDAEvent) -> None:
        """Called each time a frame is acquired."""
        self.current_event.setText(
            f"index: {event.index}\n"
            f"channel: {getattr(event.channel, 'config', 'None')}\n"
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
    frame = MDA()
    frame.show()
    app.exec_()
