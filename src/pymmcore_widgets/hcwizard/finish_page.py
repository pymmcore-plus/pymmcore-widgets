from pathlib import Path

from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import Microscope
from qtpy.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ._base_page import ConfigWizardPage

DEST_CONFIG = "dest_config"


class FinishPage(ConfigWizardPage):
    """Page for saving the configuration file."""

    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__(model, core)
        self.setTitle("Save configuration and exit")
        self.setSubTitle("All done!<br><br>Choose where to save your config file.")

        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Select a destination ...")
        self.registerField(f"{DEST_CONFIG}*", self.file_edit)

        self.select_file_btn = QPushButton("Browse...")
        self.select_file_btn.clicked.connect(self._select_file)

        row_layout = QHBoxLayout()
        row_layout.addWidget(self.file_edit)
        row_layout.addWidget(self.select_file_btn)
        self.file_edit.textChanged.connect(self.completeChanged)

        layout = QVBoxLayout(self)
        layout.addLayout(row_layout)

    def initializePage(self) -> None:
        """Called to prepare the page just before it is shown."""
        if self._model.config_file:
            self.file_edit.setText(self._model.config_file)
        self._initial_dest = self.file_edit.text()

    def validatePage(self) -> bool:
        """Validate. the page when the user clicks Next or Finish."""
        dest = self.file_edit.text()
        if dest == self._initial_dest and Path(dest).exists():
            result = QMessageBox.question(
                self,
                "File already exists",
                f"File {dest} already exists. Overwrite?",
                QMessageBox.StandardButton.No | QMessageBox.StandardButton.Yes,
            )
            if result == QMessageBox.StandardButton.No:
                return False
        return True

    def _select_file(self) -> None:
        (fname, _) = QFileDialog.getSaveFileName(
            self,
            "Select Configuration File",
            self.file_edit.text(),
            "Config Files (*.cfg)",
        )
        if fname:
            self.file_edit.setText(fname)
