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
# No longer offered: recent pymmcore-plus versions write an output path through
# ome-writers, which has no tiff-sequence format (a path without extension is
# written as OME-Zarr). Kept to read sequences saved by older versions.
TIFF_SEQ = "tiff-sequence"

# dict with writer name and extension
WRITERS: dict[str, list[str]] = {
    OME_ZARR: [".ome.zarr"],
    OME_TIFF: [".ome.tif", ".ome.tiff"],
}

EXT_TO_WRITER = {x: w for w, exts in WRITERS.items() for x in exts}
ALL_EXTENSIONS = [x for exts in WRITERS.values() for x in exts]

FILE_NAME = "Filename:"


def _known_extension(name: str) -> str | None:
    """Return a known extension if the name ends with one, ignoring case.

    Note that all non-None return values are guaranteed to be in EXTENSION_TO_WRITER.
    """
    lower = name.lower()
    return next((ext for ext in ALL_EXTENSIONS if lower.endswith(ext)), None)


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
        self.save_name.editingFinished.connect(self._update_writer_from_name)

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

        self.setFixedHeight(self.minimumSizeHint().height())

        # connect
        self.toggled.connect(self.valueChanged)
        self.save_dir.textChanged.connect(self.valueChanged)
        self.save_name.textChanged.connect(self.valueChanged)

    def currentPath(self) -> Path:
        """Return the current save destination as a Path object."""
        return Path(self.save_dir.text(), str(self.save_name.text()))

    def setCurrentPath(self, path: str | Path) -> None:
        """Set the save destination from a string or Path object."""
        path = Path(path)
        self.save_dir.setText(str(path.parent))
        self.save_name.setText(path.name)
        self._update_writer_from_name(allow_name_change=False)

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
            self.setCurrentPath(value)
            self.setChecked(True)
            return

        legacy_fmt = (fmt := value.get("format")) == TIFF_SEQ
        if legacy_fmt:
            # pymmcore-plus wrote these names without extension as OME-Zarr;
            # a name with a known extension still picks its own writer below
            self._writer_combo.setCurrentText(OME_ZARR)
            fmt = None
        elif fmt and fmt not in WRITERS:  # pragma: no cover
            raise ValueError(f"Invalid format {fmt!r}. Must be one of {list(WRITERS)}")

        self.save_dir.setText(value.get("save_dir", ""))
        self.save_name.setText(str(value.get("save_name", "")))
        self.setChecked(value.get("should_save", False))

        if fmt:
            self._writer_combo.setCurrentText(str(fmt))
        else:
            self._update_writer_from_name()

        if legacy_fmt:
            warn(
                f"The {TIFF_SEQ!r} format is no longer supported. "
                f"Using the {self._writer_combo.currentText()} writer.",
                stacklevel=2,
            )

    def _update_writer_from_name(self, allow_name_change: bool = True) -> None:
        """Called when the user finishes editing the save_name widget.

        Updates the combo box to the writer with the same extension as the save name.

        Parameters
        ----------
        allow_name_change : bool, optional
            If True (default), allow the widget to update the save_name value
            if the current name does not end with a known extension.  If False,
            the name will not be changed
        """
        name = self.save_name.text()
        if extension := _known_extension(name):
            self._writer_combo.setCurrentText(EXT_TO_WRITER[extension])
            # the writers use the lower-case extension (e.g. "x.OME.TIF" is
            # written as "x.ome.tif"), so show the name that will be written
            if allow_name_change and not name.endswith(extension):
                self.save_name.setText(name[: -len(extension)] + extension)

        elif not allow_name_change:
            # keep the current writer; the extension is added when the
            # name is next edited (e.g. before an MDA run)
            if ext := Path(name).suffix:
                warn(
                    f"Invalid format {ext!r}. "
                    f"Using the {self._writer_combo.currentText()} writer.",
                    stacklevel=2,
                )
        elif name:
            # otherwise, if the name is not empty, add the first extension from the
            # current writer
            ext = WRITERS[self._writer_combo.currentText()][0]
            self.save_name.setText(name + ext)

    def _on_browse_clicked(self) -> None:  # pragma: no cover
        """Open a dialog to select the save directory."""
        if save_dir := QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.save_dir.text()
        ):
            self.save_dir.setText(save_dir)

    def _on_writer_combo_changed(self, writer: str) -> None:
        """Called when the writer format combo box is changed.

        Updates save name to have the correct extension.
        """
        # if the name currently end with a known extension from the selected
        # writer, then we're done
        this_writer_extensions = WRITERS[writer]
        current_name = self.save_name.text()
        if _known_extension(current_name) in this_writer_extensions:
            return

        # otherwise strip any known extension and add the first one from the new writer.
        if name := _strip_known_extension(current_name):
            name += this_writer_extensions[0]
        self.save_name.setText(name)
