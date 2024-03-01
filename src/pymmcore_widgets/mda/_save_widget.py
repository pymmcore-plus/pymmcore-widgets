from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)
from superqt.utils import signals_blocked

if TYPE_CHECKING:
    from qtpy.QtGui import QFocusEvent

# dict with writer name and extension
WRITERS: dict[str, list[str]] = {
    "ome-zarr": [".ome.zarr"],
    "ome-tiff": [".ome.tiff", ".ome.tif"],
    "tiff-sequence": [""],
}
EXTENSIONS = [ext for exts in WRITERS.values() for ext in exts if ext]
FILE_NAME = "Filename:"
SUBFOLDER = "Subfolder:"


class FocusLineEdit(QLineEdit):
    """A QLineEdit that emits an editingFinished signal when it loses focus.

    This is useful in case the user does not press enter after editing the save name.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        self.editingFinished.emit()


class _SaveGroupBox(QGroupBox):
    """A Widget to gather information about MDA file saving."""

    valueChanged = Signal()

    def __init__(
        self, title: str = "Save Acquisition", parent: QWidget | None = None
    ) -> None:
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(False)

        # this is to store the extension of the selected writer
        self._extension: str = ""

        _dir_label = QLabel("Directory:")
        self.name_label = QLabel(FILE_NAME)

        self.save_dir = QLineEdit()
        self.save_dir.setPlaceholderText("Select Save Directory")
        self.save_name = FocusLineEdit()
        self.save_name.setPlaceholderText("Enter Experiment Name")
        self.save_name.editingFinished.connect(self._on_editing_finished)

        self._writer_combo = QComboBox()
        self._writer_combo.addItems(WRITERS.keys())
        self._writer_combo.currentTextChanged.connect(
            self._on_writer_combo_text_changed
        )

        browse_btn = QPushButton(text="...")
        browse_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        browse_btn.clicked.connect(self._on_browse_clicked)

        grid = QGridLayout(self)
        grid.addWidget(_dir_label, 0, 0)
        grid.addWidget(self.save_dir, 0, 1, 1, 2)
        grid.addWidget(browse_btn, 0, 3)
        grid.addWidget(self.name_label, 1, 0)
        grid.addWidget(self.save_name, 1, 1)
        grid.addWidget(self._writer_combo, 1, 2, 1, 2)

        self.setFixedHeight(self.minimumSizeHint().height())

        # connect
        self.toggled.connect(self.valueChanged)
        self.save_dir.textChanged.connect(self.valueChanged)
        self.save_name.textChanged.connect(self.valueChanged)

    def _on_browse_clicked(self) -> None:
        if save_dir := QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.save_dir.text()
        ):
            self.save_dir.setText(save_dir)

    def _on_editing_finished(self) -> None:
        """Update the save name when the user finishes editing the text."""
        extension = self._get_extension_from_name(self.save_name.text())
        writer = self._get_writer_from_extension(extension)

        # if it's a valid writer, just update the combo
        if extension and writer in WRITERS:
            self._update_combo_text(writer)

        # if the extension is not valid, clear the extension and get it form the combo
        elif name := self.save_name.text():
            self.save_name.setText(name + WRITERS[self._writer_combo.currentText()][0])

    def _get_extension_from_name(self, name: str) -> str:
        """Get the extension of the selected writer."""
        for ext in EXTENSIONS:
            if name.endswith(ext):
                return ext
        return ""

    def _get_writer_from_extension(self, extension: str) -> str:
        """Get the writer from the extension."""
        for writer, ext in WRITERS.items():
            for e in ext:
                if extension == e:
                    return writer
        raise ValueError(f"Extension {extension} not found in {WRITERS}")

    def _update_combo_text(self, writer: str) -> None:
        """Update the writer combo and trigger the text changed signal."""
        # blocking and then manually calling _on_writer_combo_text_changed because
        # if the text of the combo does not change, the currentTextChanged signal is not
        # emitted and we need it to add the extension to the name
        with signals_blocked(self._writer_combo):
            self._writer_combo.setCurrentText(writer)
        self._on_writer_combo_text_changed(writer)

    def _on_writer_combo_text_changed(self, writer: str) -> None:
        """Update the save name extension when the writer is changed."""
        self.name_label.setText(SUBFOLDER if writer == "tiff-sequence" else FILE_NAME)
        extension = self._get_extension_from_name(self.save_name.text())
        if name := self._remove_extension(self.save_name.text()):
            # get index of the extension in the list or get the first one
            # this is useful in the case of the ome-tiff writer that has two extensions
            # .ome.tiff and .ome.tif
            idx = next(
                (i for i, ext in enumerate(WRITERS[writer]) if extension == ext), 0
            )
            self.save_name.setText(name + WRITERS[writer][idx])

    def _remove_extension(self, name: str) -> str:
        """Remove the extension from the name if it's there."""
        return next((name.replace(ext, "") for ext in EXTENSIONS if ext in name), name)

    def value(self) -> str | None:
        """Return current state of the save widget."""
        if (
            not self.isChecked()
            or not self.save_dir.text()
            or not self.save_name.text()
        ):
            return None

        # returning a str because the MDASequence yaml does not support Path yet
        # maybe we can add support for Path in the future
        return str(Path(self.save_dir.text()) / self.save_name.text())

    def setValue(self, value: Path | str) -> None:
        """Set the current state of the save widget."""
        if isinstance(value, str):
            value = Path(value)

        # set the group box checked state
        self.setChecked(bool(str(value.parent)))
        # set the save directory and name
        self.save_dir.setText(str(value.parent))
        self.save_name.setText(self._remove_extension(value.name))
        # set the writer and update the combo
        extension = self._get_extension_from_name(value.name)
        writer = self._get_writer_from_extension(extension)
        self._update_combo_text(writer)
