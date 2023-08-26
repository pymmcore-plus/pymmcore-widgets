from pathlib import Path

from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import Microscope
from qtpy.QtCore import QSize
from qtpy.QtGui import QCloseEvent
from qtpy.QtWidgets import (
    QFileDialog,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
    QWizard,
)

from .defaults_page import RolesPage
from .delay_page import DelayPage
from .devices_page import DevicesPage
from .finish_page import DEST_FIELD, FinishPage
from .intro_page import IntroPage
from .labels_page import LabelsPage


class ConfigWizard(QWizard):
    """Hardware Configuration Wizard for Micro-Manager."""

    def __init__(
        self,
        config_file: str = "",
        core: CMMCorePlus | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._core = core or CMMCorePlus.instance()
        self._model = Microscope(config_file=config_file)
        self._model.load_available_devices(self._core)
        # self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        self.setWindowTitle("Hardware Configuration Wizard")
        self.addPage(IntroPage(self._model, self._core))
        self.addPage(DevicesPage(self._model, self._core))
        self.addPage(RolesPage(self._model, self._core))
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

    def microscopeModel(self) -> Microscope:
        return self._model

    def save(self, path: str | Path) -> None:
        self._model.save(path)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        answer = QMessageBox.question(
            self,
            "Save changes?",
            "Would you like to save your changes before exiting?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return
        elif answer == QMessageBox.StandardButton.Save:
            (fname, _) = QFileDialog.getSaveFileName(
                self, "Select Destination", "", "Config Files (*.cfg)"
            )
            if fname:
                self.setField(DEST_FIELD, fname)
                self.accept()
            else:
                event.ignore()
                return
        else:
            self.reject()
        return super().closeEvent(event)

    def accept(self) -> bool:
        dest = self.field(DEST_FIELD)
        dest_path = Path(dest)
        self._model.save(dest_path)
        return super().accept()
