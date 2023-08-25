from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import Microscope
from qtpy.QtCore import QSize
from qtpy.QtWidgets import QLabel, QVBoxLayout, QWidget, QWizard

from ._base_page import DelayPage, FinishPage, LabelsPage
from .defaults_page import DefaultsPage
from .devices_page import DevicesPage
from .intro_page import IntroPage


class ConfigWizard(QWizard):
    """Hardware Configuration Wizard for Micro-Manager."""

    def __init__(self, core: CMMCorePlus | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._core = core or CMMCorePlus.instance()
        self._model = Microscope.create_from_core(self._core)
        # self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        self.setWindowTitle("Hardware Configuration Wizard")
        self.addPage(IntroPage(self._model, self._core))
        self.addPage(DevicesPage(self._model, self._core))
        self.addPage(DefaultsPage(self._model, self._core))
        self.addPage(DelayPage(self._model, self._core))
        self.addPage(LabelsPage(self._model, self._core))
        self.addPage(FinishPage(self._model, self._core))

        # Create a custom widget for the side panel, to show what step we're on
        side_widget = QWidget()
        side_layout = QVBoxLayout(side_widget)
        side_layout.addStretch()
        titles = ["Config File", "Devices", "Roles", "Delays", "Labels", "Finish"]
        self.step_labels = [QLabel(f"{i + 1}. {t}") for i, t in enumerate(titles)]
        for label in self.step_labels:
            side_layout.addWidget(label)
        side_layout.addStretch()

        # Set the custom side widget
        self.setSideWidget(side_widget)

        # Connect the currentIdChanged signal to the updateStepAppearance function
        self.currentIdChanged.connect(self._update_step)
        self._update_step(self.currentId())  # Initialize the appearance

    def sizeHint(self) -> QSize:
        return super().sizeHint().expandedTo(QSize(750, 600))

    # Define a function to update step appearance
    def _update_step(self, current_index):
        for i, label in enumerate(self.step_labels):
            font = label.font()
            if i == current_index:
                font.setBold(True)
                label.setStyleSheet("color: black;")
            else:
                font.setBold(False)
                label.setStyleSheet("color: gray;")
            label.setFont(font)

    # def accept(self) -> None:
    #     return super().accept()

    # def reject(self) -> None:
    #     return super().reject()
