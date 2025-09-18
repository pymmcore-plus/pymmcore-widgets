from pathlib import Path

from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

HELP_DOC = Path(__file__).parent / "config_groups_help.html"


class ConfigGroupsHelpDialog(QDialog):
    """Help dialog for the Config Groups Editor."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Config Groups and Presets")
        self.setModal(True)

        # Add help content here
        help_text = QTextBrowser(self)
        help_text.setReadOnly(True)
        help_text.setAcceptRichText(True)
        help_text.setHtml(HELP_DOC.read_text())
        help_text.setFrameShape(QFrame.Shape.NoFrame)
        # enable links
        help_text.setOpenExternalLinks(True)

        # make the background match the dialog
        pal = self.palette()
        pal.setColor(pal.ColorRole.Base, pal.color(pal.ColorRole.Window))
        help_text.setPalette(pal)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(help_text)
        layout.addWidget(btn_box)
