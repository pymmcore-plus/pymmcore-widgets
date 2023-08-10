from typing import Any

from fonticon_mdi6 import MDI6
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QWidget
from superqt.fonticon import icon
from superqt.utils import signals_blocked
from useq import MultiPhaseTimePlan, TDurationLoops, TIntervalDuration, TIntervalLoops

from ._column_info import IntColumn, TextColumn, TimeDeltaColumn
from ._data_table import DataTableWidget


class TimeTable(DataTableWidget):
    """Table for editing a `useq-schema` time plan."""

    PHASE = TextColumn(key="phase", default=None, is_row_selector=True)
    INTERVAL = TimeDeltaColumn(key="interval", default="1 s")
    DURATION = TimeDeltaColumn(key="duration", default="0 s")
    LOOPS = IntColumn(key="loops", default=1, minimum=1)

    _active_column: int

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, parent)
        self._emitting = False

        h_header = self.table().horizontalHeader()
        h_header.setSectionsClickable(True)
        h_header.sectionClicked.connect(self._set_active_column)

        self._set_active_column(self.table().indexOf(self.LOOPS))

        # Connect the signal to update column 3 when column 4 changes
        self.valueChanged.connect(self._resolve_duration)

    def _resolve_duration(self) -> None:
        """Resolve interval, loops, duration based on which column changed.

        The rules are:
        total duration = interval * loops

        """
        if self._emitting:
            return

        table = self.table()

        changed_col = table.currentColumn()
        changed_row = table.currentRow()
        loop_col = table.indexOf(self.LOOPS)
        duration_col = table.indexOf(self.DURATION)

        plan: TIntervalDuration | TIntervalLoops
        try:
            if self._active_column == duration_col:
                plan = TIntervalDuration(**self.table().rowData(changed_row))
            else:
                plan = TIntervalLoops(**self.table().rowData(changed_row))
        except (TypeError, ValueError):
            return

        if changed_col == loop_col:
            self.DURATION.set_cell_data(table, changed_row, duration_col, plan.duration)
            self._set_active_column(loop_col)
        elif changed_col == duration_col:
            self.LOOPS.set_cell_data(table, changed_row, loop_col, plan.loops)
            self._set_active_column(duration_col)
        elif changed_col == table.indexOf(self.INTERVAL):
            if self._active_column == duration_col:
                self.LOOPS.set_cell_data(table, changed_row, loop_col, plan.loops)
            else:
                self.DURATION.set_cell_data(
                    table, changed_row, duration_col, plan.duration
                )

    def _set_active_column(self, col_idx: int) -> None:
        table = self.table()
        # only duration and loops can be set as active
        if col_idx < table.indexOf(self.DURATION):
            return
        if not (_info := table.columnInfo(col_idx)):
            return

        previous, self._active_column = getattr(self, "_active_column", None), col_idx
        if previous != self._active_column:
            with signals_blocked(self):
                for col in range(table.columnCount()):
                    if header := table.horizontalHeaderItem(col):
                        _icon = icon(MDI6.flag) if col == col_idx else QIcon()
                        header.setIcon(_icon)
            self._emitting = True
            try:
                self.valueChanged.emit()
            finally:
                self._emitting = False

    def value(
        self, exclude_unchecked: bool = True
    ) -> MultiPhaseTimePlan | TIntervalLoops | TIntervalDuration:
        """Return the current value of the table as a list of channels."""
        duration_col = self.table().indexOf(self.DURATION)
        active_key = "duration" if self._active_column == duration_col else "loops"
        phases = [
            {"interval": p["interval"], active_key: p[active_key]}
            for p in self.table().iterRecords(exclude_unchecked=exclude_unchecked)
        ]
        plan = MultiPhaseTimePlan(phases=phases)
        return plan.phases[0] if len(plan.phases) == 1 else plan  # type: ignore

    def setValue(self, value: Any) -> None:
        """Set the current value of the table."""
        if isinstance(value, MultiPhaseTimePlan):
            _phases = value.phases
        elif isinstance(value, (TDurationLoops, TIntervalLoops, TIntervalDuration)):
            _phases = [value]
        else:
            raise TypeError(f"Expected useq TimePlan, got {type(value)}.")
        if not _phases:
            self.table().setRowCount(0)
            return

        super().setValue([p.model_dump(exclude_unset=True) for p in _phases])

        if isinstance(_phases[0], (TIntervalDuration)):
            self._set_active_column(self.table().indexOf(self.DURATION))
        else:
            self._set_active_column(self.table().indexOf(self.LOOPS))
