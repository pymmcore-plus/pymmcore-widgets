import logging

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

from ._base_page import _ConfigWizardPage

logger = logging.getLogger(__name__)


class IntroPage(_ConfigWizardPage):
    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__(model, core)
        self.setTitle("Select Configuration File")
        self.setSubTitle(
            "This wizard will walk you through setting up the hardware in your system."
        )

        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        self.file_edit.setPlaceholderText("Select a configuration file...")
        self.select_file_btn = QPushButton("Browse...")
        self.select_file_btn.clicked.connect(self.select_file)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.addWidget(self.file_edit)
        row_layout.addWidget(self.select_file_btn)

        self.new_btn = QRadioButton("Create new configuration")
        self.new_btn.clicked.connect(row.setDisabled)
        self.modify_btn = QRadioButton("Modify or explore existing configuration")
        self.modify_btn.clicked.connect(row.setEnabled)

        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.new_btn)
        self.btn_group.addButton(self.modify_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.new_btn)
        layout.addWidget(self.modify_btn)
        layout.addWidget(row)

        # load settings:
        if self._model.config_file:
            self.file_edit.setText(self._model.config_file)
            self.modify_btn.click()
        else:
            self.new_btn.click()

    def select_file(self) -> None:
        (fname, _) = QFileDialog.getOpenFileName(
            self, "Select Configuration File", "", "Config Files (*.cfg)"
        )
        if fname:
            self.file_edit.setText(fname)

    def cleanupPage(self) -> None:
        self._model.reset()
        try:
            self._core.unloadAllDevices()
        except Exception as e:
            logger.exception(e)

        self.file_edit.setText(self._model.config_file)
        return super().cleanupPage()

    def validatePage(self) -> bool:
        if self.btn_group.checkedButton() is self.new_btn:
            self._model = Microscope()
        else:
            self._model = Microscope(config_file=self.file_edit.text())
        return super().validatePage()
