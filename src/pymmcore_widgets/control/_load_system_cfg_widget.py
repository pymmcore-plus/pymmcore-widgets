from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from pymmcore_widgets._util import load_system_config


class ConfigurationWidget(QWidget):
    """A Widget to select and load a micromanager system configuration.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget. By default, None.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self.cfg_LineEdit = QLineEdit()
        self.cfg_LineEdit.setPlaceholderText("MMConfig_demo.cfg")

        self.browse_cfg_Button = QPushButton("...")
        self.browse_cfg_Button.clicked.connect(self._browse_cfg)

        self.load_cfg_Button = QPushButton("Load")
        self.load_cfg_Button.clicked.connect(self._load_cfg)

        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.cfg_LineEdit)
        self.layout().addWidget(self.browse_cfg_Button)
        self.layout().addWidget(self.load_cfg_Button)

    def _browse_cfg(self) -> None:
        """Open file dialog to select a config file."""
        (filename, _) = QFileDialog.getOpenFileName(
            self, "Select a Micro-Manager configuration file", "", "cfg(*.cfg)"
        )
        if filename:
            self.cfg_LineEdit.setText(filename)

    def _load_cfg(self) -> None:
        """Load the config path currently in the line_edit."""
        load_system_config(self.cfg_LineEdit.text(), self._mmc)

    def setTitle(self, title: str) -> None:
        _show_deprecation("setTitle")

    def title(self) -> str:
        _show_deprecation("title")
        return ""


def _show_deprecation(name: str) -> None:
    import warnings

    warnings.warn(
        "ConfigurationWidget is no longer a QGroupBox. "
        f"Please place it in a groupbox if you need {name}",
        DeprecationWarning,
        stacklevel=3,
    )
