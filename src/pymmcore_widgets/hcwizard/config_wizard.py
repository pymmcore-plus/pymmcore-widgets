from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus, Keyword
from pymmcore_plus.model import Microscope
from qtpy.QtCore import QSize
from qtpy.QtWidgets import (
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

logger = logging.getLogger(__name__)


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
        self._original_config = self._core.systemConfigurationFile() or ""
        self._model = Microscope()
        self._model.load_available_devices(self._core)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

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
                "Discard changes?",
                "You have unsaved changes. Discard and close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.No:
                event.ignore()
                return
        self.reject()
        super().closeEvent(event)

    def accept(self) -> None:
        """Accept the wizard and save the configuration to a file."""
        dest = self.field(DEST_CONFIG)
        dest_path = Path(dest)

        # Remove stale config entries referencing devices no longer in the model.
        # Matches Java's MicroscopeModel.checkConfigurations().
        self._check_configurations()

        self._model.save(dest_path)

        # Unload all devices and reload from the saved file so that the core
        # state cleanly matches the file on disk.  This matches the Java
        # ConfigMenu.runHardwareWizard() post-wizard reload step.
        try:
            self._core.unloadAllDevices()
        except Exception:
            logger.exception("Failed to unload devices after save")
        try:
            self._core.loadSystemConfiguration(str(dest_path))
        except Exception:
            logger.exception("Failed to reload saved configuration")

        super().accept()

    def reject(self) -> None:
        """Reject the wizard and restore the prior core state."""
        super().reject()
        try:
            self._core.unloadAllDevices()
        except Exception:
            pass
        if self._original_config and os.path.isfile(self._original_config):
            try:
                self._core.loadSystemConfiguration(self._original_config)
            except Exception:
                pass

    def _check_configurations(self) -> None:
        """Remove stale settings from config groups and pixel size presets.

        Mirrors Java MicroscopeModel.checkConfigurations(): for every config
        group / pixel-size preset, drop any Setting whose device_name does not
        match a device currently in the model.  Empty presets and empty groups
        are removed entirely.
        """
        device_names = {d.name for d in self._model.devices}
        device_names.add(Keyword.CoreDevice.value)

        # --- config groups ---
        groups_to_remove: list[str] = []
        for group in self._model.config_groups.values():
            presets_to_remove: list[str] = []
            for preset in group.presets.values():
                preset.settings = [
                    s for s in preset.settings if s.device_name in device_names
                ]
                if not preset.settings:
                    presets_to_remove.append(preset.name)
            for name in presets_to_remove:
                del group.presets[name]
            if not group.presets:
                groups_to_remove.append(group.name)
        for name in groups_to_remove:
            del self._model.config_groups[name]

        # --- pixel size presets ---
        px = self._model.pixel_size_group
        px_presets_to_remove: list[str] = []
        for preset in px.presets.values():
            preset.settings = [
                s for s in preset.settings if s.device_name in device_names
            ]
            if not preset.settings:
                px_presets_to_remove.append(preset.name)
        for name in px_presets_to_remove:
            del px.presets[name]

    def _update_step(self, current_index: int) -> None:
        """Change text on the left when the page changes."""
        for i, label in enumerate(self.step_labels):
            font = label.font()
            if i == current_index:
                font.setBold(True)
            else:
                font.setBold(False)
            label.setFont(font)
