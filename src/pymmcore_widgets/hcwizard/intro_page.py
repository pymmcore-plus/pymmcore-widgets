import logging
import os

from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import Microscope
from qtpy.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ._base_page import ConfigWizardPage

logger = logging.getLogger(__name__)

SRC_CONFIG = "src_config"
EXISTING_CONFIG = "EXISTING_CONFIG"


class IntroPage(ConfigWizardPage):
    """First page, for selecting new or existing configuration."""

    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__(model, core)
        self.setTitle("Select Configuration File")
        self.setSubTitle(
            "This wizard will walk you through setting up the hardware in your system."
        )

        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        self.file_edit.setPlaceholderText("Select a configuration file...")
        self.registerField(SRC_CONFIG, self.file_edit)

        self.select_file_btn = QPushButton("Browse...")
        self.select_file_btn.clicked.connect(self._select_file)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.addWidget(self.file_edit)
        row_layout.addWidget(self.select_file_btn)

        self.new_btn = QRadioButton("Create new configuration")
        self.new_btn.clicked.connect(lambda: row.setDisabled(True))

        self.modify_btn = QRadioButton("Modify or explore existing configuration")
        self.modify_btn.clicked.connect(lambda: row.setEnabled(True))
        self.registerField(EXISTING_CONFIG, self.modify_btn)

        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.new_btn)
        self.btn_group.addButton(self.modify_btn)

        self.btn_group.buttonClicked.connect(self.completeChanged)
        self.file_edit.textChanged.connect(self.completeChanged)

        layout = QVBoxLayout(self)
        layout.addWidget(self.new_btn)
        layout.addWidget(self.modify_btn)
        layout.addWidget(row)

    def _select_file(self) -> None:
        (fname, _) = QFileDialog.getOpenFileName(
            self, "Select Configuration File", "", "Config Files (*.cfg)"
        )
        if fname:
            self.file_edit.setText(fname)

    def initializePage(self) -> None:
        """Called to prepare the page just before it is shown."""
        if self.field(SRC_CONFIG):
            self.modify_btn.click()
        else:
            self.new_btn.click()

    def cleanupPage(self) -> None:
        """Called to reset the page's contents when the user clicks BACK."""
        self._model.reset()
        try:
            self._core.unloadAllDevices()
        except Exception as e:
            logger.exception(e)

        self.file_edit.setText(self._model.config_file)
        super().cleanupPage()

    def validatePage(self) -> bool:
        """Validate the page when the user clicks Next or Finish."""
        if self.btn_group.checkedButton() is self.new_btn:
            self._model.reset()
            try:
                self._core.unloadAllDevices()
            except Exception as e:
                logger.exception(e)
        else:
            self._model.load_config(self.file_edit.text())
        self._model.mark_clean()
        return super().validatePage()  # type: ignore

    def isComplete(self) -> bool:
        """Called to determine whether the Next/Finish button should be enabled."""
        return bool(
            self.btn_group.checkedButton() is not self.modify_btn
            or os.path.isfile(self.file_edit.text())
        )
