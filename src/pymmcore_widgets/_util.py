from typing import Optional, Sequence

from qtpy.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class ComboMessageBox(QDialog):
    """Dialog that presents a combo box of `items`."""

    def __init__(
        self,
        items: Sequence[str] = (),
        text: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._combo = QComboBox()
        self._combo.addItems(items)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel  # noqa
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)

        self.setLayout(QVBoxLayout())
        if text:
            self.layout().addWidget(QLabel(text))
        self.layout().addWidget(self._combo)
        self.layout().addWidget(btn_box)

    def currentText(self) -> str:
        """Returns the current QComboBox text."""
        return self._combo.currentText()  # type: ignore [no-any-return]
