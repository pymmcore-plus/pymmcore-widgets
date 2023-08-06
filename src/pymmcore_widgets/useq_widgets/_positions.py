import json
from pathlib import Path
from typing import Sequence, cast

import useq
from qtpy.QtWidgets import QFileDialog, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ._column_info import FloatColumn, TextColumn
from ._data_table import DataTableWidget


class PositionTable(DataTableWidget):
    """Table for editing a list of `useq.Positions`."""

    POSITION = TextColumn(key="name", default="#{idx}", is_row_selector=True)
    X = FloatColumn(key="x", header="X [mm]", default=0.0)
    Y = FloatColumn(key="y", header="Y [mm]", default=0.0)
    Z = FloatColumn(key="z", header="Z [mm]", default=0.0)

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, parent)

        layout = cast("QVBoxLayout", self.layout())

        self._save_button = QPushButton("Save...")
        self._save_button.clicked.connect(self.save)
        self._load_button = QPushButton("Load...")
        self._load_button.clicked.connect(self.load)
        self._custom_button = QPushButton("Custom...")
        self._custom_button.clicked.connect(self._custom)
        # self._optimize_button = QPushButton("Optimize...")
        # self._optimize_button.clicked.connect(self._optimize)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._save_button)
        btn_row.addWidget(self._load_button)
        btn_row.addWidget(self._custom_button)
        # btn_row.addWidget(self._optimize_button)

        layout.addLayout(btn_row)

    def value(self, exclude_unchecked: bool = True) -> list[useq.Position]:
        """Return the current value of the table as a list of channels."""
        return [
            useq.Position(**r)
            for r in self.table().iterRecords(exclude_unchecked=exclude_unchecked)
        ]

    def setValue(self, value: Sequence[useq.Position]) -> None:  # type: ignore
        """Set the current value of the table."""
        _values = []
        for v in value:
            if not isinstance(v, useq.Position):
                raise TypeError(f"Expected useq.Position, got {type(v)}")
            _values.append(v.model_dump(exclude_unset=True))
        super().setValue(_values)

    def save(self, file: str | Path | None = None) -> None:
        """Save the current positions to a file."""
        if not isinstance(file, (str, Path)):
            file, _ = QFileDialog.getSaveFileName(
                self, "Save MDASequence and filename.", "", "json(*.json)"
            )
            if not file:
                return

        dest = Path(file)
        if not dest.suffix:
            dest = dest.with_suffix(".json")

        if dest.suffix != ".json":
            raise ValueError(f"Invalid file extension: {dest.suffix!r}, expected .json")

        data = json.dumps([x.model_dump() for x in self.value()], indent=2)
        dest.write_text(data)

    def load(self, file: str | Path | None = None) -> None:
        """Load positions from a file."""
        if not isinstance(file, (str, Path)):
            file, _ = QFileDialog.getOpenFileName(
                self, "Select an MDAsequence file.", "", "json(*.json)"
            )
            if not file:
                return

        src = Path(file)
        if not src.is_file():
            raise FileNotFoundError(f"File not found: {src}")

        try:
            data = json.loads(src.read_text())
            self.setValue([useq.Position(**d) for d in data])
        except Exception as e:
            raise ValueError(f"Failed to load MDASequence file: {src}") from e

    def _custom(self) -> None:
        """Customize positions."""
        print("Not Implemented")

    def _optimize(self) -> None:
        """Optimize positions."""
        print("Not Implemented")
