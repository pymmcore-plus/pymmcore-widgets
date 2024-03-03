from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from warnings import warn

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

if TYPE_CHECKING:
    from typing import TypedDict

    from qtpy.QtGui import QFocusEvent

    class SaveInfo(TypedDict):
        save_dir: str
        save_name: str
        format: str
        should_save: bool


OME_ZARR = "ome-zarr"
OME_TIFF = "ome-tiff"
TIFF_SEQ = "tiff-sequence"

# dict with writer name and extension
WRITERS: dict[str, list[str]] = {
    OME_ZARR: [".ome.zarr"],
    OME_TIFF: [".ome.tif", ".ome.tiff"],
    TIFF_SEQ: [""],
}

EXT_TO_WRITER = {x: w for w, exts in WRITERS.items() for x in exts}
ALL_EXTENSIONS = [x for exts in WRITERS.values() for x in exts if x]
DIRECTORY_WRITERS = {TIFF_SEQ}  # technically could be zarr too

FILE_NAME = "Filename:"
SUBFOLDER = "Subfolder:"


def _known_extension(name: str) -> str | None:
    """Return a known extension if the name ends with one.

    Note that all non-None return values are guaranteed to be in EXTENSION_TO_WRITER.
    """
    return next((ext for ext in ALL_EXTENSIONS if name.endswith(ext)), None)


def _strip_known_extension(name: str) -> str:
    """Strip a known extension from the name if it ends with one."""
    if ext := _known_extension(name):
        name = name[: -len(ext)]
    return name.rstrip(".").rstrip()  # remove trailing dots and spaces


class _FocusOutLineEdit(QLineEdit):
    """A QLineEdit that emits an editingFinished signal when it loses focus.

    This is useful in case the user does not press enter after editing the save name.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

    def focusOutEvent(self, event: QFocusEvent | None) -> None:  # pragma: no cover
        super().focusOutEvent(event)
        self.editingFinished.emit()


class SaveGroupBox(QGroupBox):
    """A Widget to gather information about MDA file saving."""

    valueChanged = Signal()

    def __init__(
        self, title: str = "Save Acquisition", parent: QWidget | None = None
    ) -> None:
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(False)

        self.name_label = QLabel(FILE_NAME)

        self.save_dir = QLineEdit()
        self.save_dir.setPlaceholderText("Select Save Directory")
        self.save_name = _FocusOutLineEdit()
        self.save_name.setPlaceholderText("Enter Experiment Name")
        self.save_name.editingFinished.connect(self._on_editing_finished)

        self._writer_combo = QComboBox()
        self._writer_combo.addItems(list(WRITERS))
        self._writer_combo.currentTextChanged.connect(self._on_writer_combo_changed)

        browse_btn = QPushButton(text="...")
        browse_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        browse_btn.clicked.connect(self._on_browse_clicked)

        grid = QGridLayout(self)
        grid.addWidget(QLabel("Directory:"), 0, 0)
        grid.addWidget(self.save_dir, 0, 1, 1, 2)
        grid.addWidget(browse_btn, 0, 3)
        grid.addWidget(self.name_label, 1, 0)
        grid.addWidget(self.save_name, 1, 1)
        grid.addWidget(self._writer_combo, 1, 2, 1, 2)

        # prevent jiggling when toggling the checkbox
        width = self.fontMetrics().horizontalAdvance(SUBFOLDER)
        grid.setColumnMinimumWidth(0, width)
        self.setFixedHeight(self.minimumSizeHint().height())

        # connect
        self.toggled.connect(self.valueChanged)
        self.save_dir.textChanged.connect(self.valueChanged)
        self.save_name.textChanged.connect(self.valueChanged)

    def value(self) -> SaveInfo:
        """Return current state of the save widget."""
        return {
            "save_dir": self.save_dir.text(),
            "save_name": self.save_name.text(),
            "format": self._writer_combo.currentText(),
            "should_save": self.isChecked(),
        }

    def setValue(self, value: dict | str | Path) -> None:
        """Set the current state of the save widget.

        If value is a dict, keys should be:
        - save_dir: str - Set the save directory.
        - save_name: str - Set the save name.
        - format: str - Set the combo box to the writer with this name.
        - should_save: bool - Set the checked state of the checkbox.
        """
        if isinstance(value, (str, Path)):
            path = Path(value)
            value = {
                "save_dir": str(path.parent),
                "save_name": path.name,
                "should_save": True,
            }

        self.save_dir.setText(value.get("save_dir", ""))
        save_name = str(value.get("save_name", ""))
        self.save_name.setText(save_name)
        self.setChecked(value.get("should_save", False))

        # retrieve writer from the format key.
        fmt = value.get("format")
        if fmt is None and (ext := _known_extension(save_name)):
            fmt = EXT_TO_WRITER[ext]

        if fmt not in WRITERS:
            if ext := Path(save_name).suffix:
                warn(f"Invalid format {ext!r}. Defaulting to {TIFF_SEQ}.", stacklevel=2)
            fmt = TIFF_SEQ

        # set the writer and update the combo
        self._writer_combo.setCurrentText(fmt)

    def _on_browse_clicked(self) -> None:  # pragma: no cover
        """Open a dialog to select the save directory."""
        if save_dir := QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.save_dir.text()
        ):
            self.save_dir.setText(save_dir)

    def _on_editing_finished(self) -> None:
        """Called when the user finishes editing the save_name widget.

        Updates the combo box to the writer with the same extension as the save name.
        """
        if extension := _known_extension(self.save_name.text()):
            self._writer_combo.setCurrentText(EXT_TO_WRITER[extension])

        # if the extension is not valid, clear the extension and get it form the combo
        elif name := self.save_name.text():
            ext = WRITERS[self._writer_combo.currentText()][0]
            self.save_name.setText(name + ext)

    def _on_writer_combo_changed(self, writer: str) -> None:
        """Called when the writer format combo box is changed.

        Updates save name to have the correct extension, and updates the label to
        "Subfolder" or "Filename" depending on the writer type
        """
        # update the label
        self.name_label.setText(SUBFOLDER if writer in DIRECTORY_WRITERS else FILE_NAME)

        # if the name currently end with a known extension from the selected
        # writer, then we're done
        this_writer_extensions = WRITERS[writer]
        current_name = self.save_name.text()
        for ext in this_writer_extensions:
            if ext and current_name.endswith(ext):
                return

        # otherwise strip any known extension and add the first one from the new writer.
        if name := _strip_known_extension(current_name):
            name += this_writer_extensions[0]
        self.save_name.setText(name)
