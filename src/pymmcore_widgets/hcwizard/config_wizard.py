from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import Microscope
from qtpy.QtCore import QSize
from qtpy.QtWidgets import (
    QFileDialog,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
    QWizard,
)

from .delay_page import DelayPage
from .devices_page import DevicesPage
from .finish_page import DEST_CONFIG, FinishPage
from .intro_page import SRC_CONFIG, IntroPage
from .labels_page import LabelsPage
from .roles_page import RolesPage

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent


class ConfigWizard(QWizard):
    """Hardware Configuration Wizard for Micro-Manager.

    It can be used to create a new configuration file or edit an existing one.

    Parameters
    ----------
    config_file : str, optional
        Path to a configuration file to load, by default "".
    core : CMMCorePlus, optional
        A CMMCorePlus instance, by default, uses the global singleton.
    parent : QWidget, optional
        The parent widget, by default None.
    """

    def __init__(
        self,
        config_file: str = "",
        core: CMMCorePlus | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._core = core or CMMCorePlus.instance()
        self._model = Microscope()
        self._model.load_available_devices(self._core)
        # self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        self.setWindowTitle("Hardware Configuration Wizard")
        self.addPage(IntroPage(self._model, self._core))
        self.addPage(DevicesPage(self._model, self._core))
        self.addPage(RolesPage(self._model, self._core))
        self.addPage(DelayPage(self._model, self._core))
        self.addPage(LabelsPage(self._model, self._core))
        self.addPage(FinishPage(self._model, self._core))

        self.setField(SRC_CONFIG, config_file)

        # Create a custom widget for the side panel, to show what step we're on
        side_widget = QWidget(self)
        side_layout = QVBoxLayout(side_widget)
        side_layout.addStretch()
        titles = ["Config File", "Devices", "Roles", "Delays", "Labels", "Finish"]
        self.step_labels = [QLabel(f"{i + 1}. {t}") for i, t in enumerate(titles)]
        for label in self.step_labels:
            side_layout.addWidget(label)
        side_layout.addStretch()

        # Set the custom side widget
        self.setSideWidget(side_widget)

        self.currentIdChanged.connect(self._update_step)
        self._update_step(self.currentId())  # Initialize the appearance

    def sizeHint(self) -> QSize:
        """Return the size hint for the wizard."""
        return super().sizeHint().expandedTo(QSize(750, 600))

    def microscopeModel(self) -> Microscope:
        """Return the microscope model."""
        return self._model

    def save(self, path: str | Path) -> None:
        """Save the configuration to a file."""
        self._model.save(path)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Called when the window is closed."""
        if not event:
            return
        if self._model.is_dirty():
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
                    self.setField(DEST_CONFIG, fname)
                    self.accept()
                else:
                    event.ignore()
                    return
            else:
                self.reject()
        super().closeEvent(event)

    def accept(self) -> None:
        """Accept the wizard and save the configuration to a file."""
        dest = self.field(DEST_CONFIG)
        dest_path = Path(dest)
        self._model.save(dest_path)
        super().accept()

    def reject(self) -> None:
        """Reject the wizard and reload the prior configuration."""
        super().reject()
        last_config_file = self._core.systemConfigurationFile()
        if last_config_file is not None:
            self._core.loadSystemConfiguration(last_config_file)

    def _update_step(self, current_index: int) -> None:
        """Change text on the left when the page changes."""
        for i, label in enumerate(self.step_labels):
            font = label.font()
            if i == current_index:
                font.setBold(True)
                label.setStyleSheet("color: black;")
            else:
                font.setBold(False)
                label.setStyleSheet("color: gray;")
            label.setFont(font)
