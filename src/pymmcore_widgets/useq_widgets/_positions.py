from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, cast

import useq
from fonticon_mdi6 import MDI6
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon

from ._column_info import FloatColumn, TextColumn, WdgGetSet, WidgetColumn
from ._data_table import DataTableWidget

OK_CANCEL = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
NULL_SEQUENCE = useq.MDASequence()
MAX = 9999999


class _MDAPopup(QDialog):
    def __init__(
        self, value: useq.MDASequence | None = None, parent: QWidget | None = None
    ) -> None:
        from ._mda_sequence import MDATabs

        super().__init__(parent)

        # create a new MDA tab widget without the stage positions tab
        self.mda_tabs = MDATabs(self)
        self.mda_tabs.removeTab(self.mda_tabs.indexOf(self.mda_tabs.stage_positions))

        # use the parent's channel groups if possible
        par = self.parent()
        while par:
            if isinstance(par, MDATabs):
                self.mda_tabs.channels.setChannelGroups(par.channels.channelGroups())
                break
            par = par.parent()

        # set the value if provided
        if value:
            self.mda_tabs.setValue(value)

        # create ok and cancel buttons
        self._btns = QDialogButtonBox(OK_CANCEL)
        self._btns.accepted.connect(self.accept)
        self._btns.rejected.connect(self.reject)

        # create layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.mda_tabs)
        layout.addWidget(self._btns)


class MDAButton(QWidget):
    valueChanged = Signal()
    _value: useq.MDASequence | None

    def __init__(self) -> None:
        super().__init__()
        self.seq_btn = QPushButton()
        self.seq_btn.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.seq_btn.clicked.connect(self._on_click)
        self.seq_btn.setIcon(icon(MDI6.axis))

        self.clear_btn = QPushButton()
        self.clear_btn.setIcon(icon(MDI6.close_circle, color="red"))
        self.clear_btn.setFixedWidth(20)
        self.clear_btn.hide()
        self.clear_btn.clicked.connect(lambda: self.setValue(None))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)
        layout.addWidget(self.seq_btn)
        layout.addWidget(self.clear_btn)

        self.setValue(None)

    def _on_click(self) -> None:
        dialog = _MDAPopup(self._value, self)
        if dialog.exec():
            self.setValue(dialog.mda_tabs.value())

    def value(self) -> useq.MDASequence | None:
        return self._value

    def setValue(self, value: useq.MDASequence | dict | None) -> None:
        if isinstance(value, dict):
            value = useq.MDASequence(**value)
        elif value and not isinstance(value, useq.MDASequence):  # pragma: no cover
            raise TypeError(f"Expected useq.MDASequence, got {type(value)}")
        old_val, self._value = getattr(self, "_value", None), value
        if old_val != value:
            # if sub-sequence is equal to the null sequence (useq.MDASequence())
            # treat it as None
            if value and value != NULL_SEQUENCE:
                self.seq_btn.setIcon(icon(MDI6.axis_arrow, color="green"))
                self.clear_btn.show()
            else:
                self.seq_btn.setIcon(icon(MDI6.axis))
                self.clear_btn.hide()
            self.valueChanged.emit()


_MDAButton = WdgGetSet(
    MDAButton,
    MDAButton.value,
    MDAButton.setValue,
    lambda w, cb: w.valueChanged.connect(cb),
)


@dataclass(frozen=True)
class SubSeqColumn(WidgetColumn):
    """Column for editing a `useq.MDASequence`."""

    data_type: WdgGetSet = _MDAButton


class PositionTable(DataTableWidget):
    """Table for editing a list of `useq.Positions`."""

    NAME = TextColumn(key="name", default=None, is_row_selector=True)
    X = FloatColumn(key="x", header="X [mm]", default=0.0, maximum=MAX, minimum=-MAX)
    Y = FloatColumn(key="y", header="Y [mm]", default=0.0, maximum=MAX, minimum=-MAX)
    Z = FloatColumn(key="z", header="Z [mm]", default=0.0, maximum=MAX, minimum=-MAX)
    AF = FloatColumn(key="af", header="AF", default=0.0, maximum=MAX, minimum=-MAX)
    SEQ = SubSeqColumn(key="sequence", header="Sub-Sequence", default=None)

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, parent)

        self.include_z = QCheckBox("Include Z")
        self.include_z.setChecked(True)
        self.include_z.toggled.connect(self._on_include_z_toggled)

        self.use_af = QCheckBox("Use Autofocus")
        self.use_af.toggled.connect(self._on_use_af_toggled)
        # not calling _on_use_af_toggled here because it will create issue on the
        # connected core version
        af_col = self.table().indexOf(self.AF)
        self.table().setColumnHidden(af_col, True)

        self._save_button = QPushButton("Save...")
        self._save_button.clicked.connect(self.save)
        self._load_button = QPushButton("Load...")
        self._load_button.clicked.connect(self.load)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(15)
        btn_row.addWidget(self.include_z)
        btn_row.addWidget(self.use_af)
        btn_row.addStretch()
        btn_row.addWidget(self._save_button)
        btn_row.addWidget(self._load_button)

        layout = cast("QVBoxLayout", self.layout())
        layout.addLayout(btn_row)

    def _get_autofocus_plan(self, af_offset: float) -> useq.AxesBasedAF:
        return useq.AxesBasedAF(autofocus_motor_offset=af_offset, axes=("p",))  # type: ignore  # noqa E501

    def value(
        self, exclude_unchecked: bool = True, exclude_hidden_cols: bool = True
    ) -> tuple[useq.Position, ...]:
        """Return the current value of the table as a list of channels."""
        out = []
        for r in self.table().iterRecords(
            exclude_unchecked=exclude_unchecked, exclude_hidden_cols=exclude_hidden_cols
        ):
            if not r.get(self.NAME.key, True):
                r.pop(self.NAME.key, None)

            if not self.use_af.isChecked():
                pos = useq.Position(**r)
            else:
                pos = useq.Position(**r)
                af_offset = r.get(self.AF.key, None)
                if pos.sequence is None:
                    # if there is no sub-sequence, create a new one with the autofocus
                    pos = pos.replace(
                        sequence=useq.MDASequence(
                            autofocus_plan=self._get_autofocus_plan(af_offset)
                        )
                    )
                else:
                    # if there is a sub-sequence, add the autofocus plan to it
                    pos = pos.replace(
                        sequence=pos.sequence.replace(
                            autofocus_plan=self._get_autofocus_plan(af_offset)
                        )
                    )

            out.append(pos)
        return tuple(out)

    def setValue(self, value: Sequence[useq.Position]) -> None:  # type: ignore
        """Set the current value of the table."""
        _values = []
        _use_af = False
        # _af_z_devices: set[str] = set()
        for v in value:
            if not isinstance(v, useq.Position):  # pragma: no cover
                raise TypeError(f"Expected useq.Position, got {type(v)}")

            _af = {}
            if v.sequence is not None and v.sequence.autofocus_plan is not None:
                # if the sub-sequence is empty, set it to None. Else we simply
                # exclude the autofocus plan
                sub_seq_dict = v.sequence.model_dump(
                    exclude_unset=True, exclude={"autofocus_plan"}
                )
                sub_seq = useq.MDASequence(**sub_seq_dict) if sub_seq_dict else None

                # get autofocus plan device name and offset
                _af_offset = v.sequence.autofocus_plan.autofocus_motor_offset

                # set the autofocus offset that will be added to the table
                _af = {self.AF.key: _af_offset}

                # remopve autofocus plan from sub-sequence
                v = v.replace(sequence=sub_seq)

                _use_af = True

            _values.append({**v.model_dump(exclude_unset=True), **_af})

        self.use_af.setChecked(_use_af)

        super().setValue(_values)

    def save(self, file: str | Path | None = None) -> None:
        """Save the current positions to a file."""
        if not isinstance(file, (str, Path)):
            file, _ = QFileDialog.getSaveFileName(
                self, "Save MDASequence and filename.", "", "json(*.json)"
            )
            if not file:
                return  # pragma: no cover

        dest = Path(file)
        if not dest.suffix:
            dest = dest.with_suffix(".json")

        if dest.suffix != ".json":  # pragma: no cover
            raise ValueError(f"Invalid file extension: {dest.suffix!r}, expected .json")

        # doing it this way because model_json_dump knows how to serialize everything.
        inner = ",\n".join([x.model_dump_json() for x in self.value()])
        dest.write_text(f"[\n{inner}\n]\n")

    def load(self, file: str | Path | None = None) -> None:
        """Load positions from a file."""
        if not isinstance(file, (str, Path)):
            file, _ = QFileDialog.getOpenFileName(
                self, "Select an MDAsequence file.", "", "json(*.json)"
            )
            if not file:
                return  # pragma: no cover

        src = Path(file)
        if not src.is_file():  # pragma: no cover
            raise FileNotFoundError(f"File not found: {src}")

        try:
            data = json.loads(src.read_text())
            self.setValue([useq.Position(**d) for d in data])
        except Exception as e:  # pragma: no cover
            raise ValueError(f"Failed to load MDASequence file: {src}") from e

    def _on_include_z_toggled(self, checked: bool) -> None:
        z_col = self.table().indexOf(self.Z)
        self.table().setColumnHidden(z_col, not checked)
        self.valueChanged.emit()

    def _on_use_af_toggled(self, checked: bool) -> None:
        af_col = self.table().indexOf(self.AF)
        self.table().setColumnHidden(af_col, not checked)
        self.valueChanged.emit()
