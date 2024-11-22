from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fonticon_mdi6 import MDI6
from qtpy.QtGui import QIcon
from superqt.fonticon import icon
from superqt.utils import signals_blocked
from useq import MultiPhaseTimePlan, TDurationLoops, TIntervalDuration, TIntervalLoops

from ._column_info import IntColumn, TextColumn, TimeDeltaColumn
from ._data_table import DataTableWidget

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget


class TimePlanWidget(DataTableWidget):
    """Table to edit a [useq.TimePlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#time-plans)."""

    PHASE = TextColumn(key="phase", default=None, is_row_selector=True)
    INTERVAL = TimeDeltaColumn(key="interval", default="1 s")
    DURATION = TimeDeltaColumn(key="duration", default="0 s")
    LOOPS = IntColumn(key="loops", default=1, minimum=1)

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, parent)
        self._emitting = False
        self._mode_column: int | None = None

        h_header = self.table().horizontalHeader()
        h_header.setSectionsClickable(True)
        h_header.sectionClicked.connect(self._set_mode_column)

        self._set_mode_column(self.table().indexOf(self.LOOPS))

        self.valueChanged.connect(self._on_value_changed)

    # ------------------------- Public API -------------------------

    def value(
        self, exclude_unchecked: bool = True
    ) -> MultiPhaseTimePlan | TIntervalLoops | TIntervalDuration:
        """Return the current value of the table as a [useq.TimePlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#time-plans).

        Returns
        -------
        MultiPhaseTimePlan | TIntervalLoops | TIntervalDuration
            The current [useq.TimePlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#time-plans)
            value of the table.
        """
        duration_col = self.table().indexOf(self.DURATION)
        active_key = "duration" if self._mode_column == duration_col else "loops"
        phases = [
            {"interval": p["interval"], active_key: p[active_key]}
            for p in self.table().iterRecords(exclude_unchecked=exclude_unchecked)
        ]
        plan = MultiPhaseTimePlan(phases=phases)
        return plan.phases[0] if len(plan.phases) == 1 else plan  # type: ignore

    def setValue(self, value: Any) -> None:
        """Set the current value of the table from a [useq.TimePlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#time-plans).

        Parameters
        ----------
        value : MultiPhaseTimePlan | TIntervalLoops | TDurationLoops | TIntervalDuration | None
            The
            [useq.TimePlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#time-plans)
            to set.
        """  # noqa: E501
        if isinstance(value, MultiPhaseTimePlan):
            _phases = value.phases
        elif isinstance(value, (TDurationLoops, TIntervalLoops, TIntervalDuration)):
            _phases = [value]
        elif value is None:
            _phases = []
        else:
            raise TypeError(f"Expected useq.TimePlan or None, got {type(value)}.")
        if not _phases:
            self.table().setRowCount(0)
            return

        super().setValue([p.model_dump(exclude_unset=True) for p in _phases])

        col_idx = self.table().indexOf(
            self.DURATION if isinstance(_phases[0], TIntervalDuration) else self.LOOPS
        )
        self.table().setCurrentCell(self.table().rowCount() - 1, col_idx)
        self._resolve_duration()

    # ------------------------- Private API -------------------------

    def _on_value_changed(self) -> None:
        self._resolve_duration()

    def _resolve_duration(self) -> None:
        """Resolve interval, loops, duration based on which column changed.

        The rules are:
        total duration = interval * loops
        """
        if self._emitting:
            return  # pragma: no cover

        _current_col = self.table().currentColumn()
        _current_row = self.table().currentRow()
        self._set_mode_column(_current_col)

        table = self.table()
        loop_col = table.indexOf(self.LOOPS)
        duration_col = table.indexOf(self.DURATION)

        plan: TIntervalDuration | TIntervalLoops
        data = self.table().rowData(_current_row)
        try:
            if self._mode_column == duration_col:
                plan = TIntervalDuration(
                    interval=data[self.INTERVAL.key], duration=data[self.DURATION.key]
                )
            else:
                plan = TIntervalLoops(
                    interval=data[self.INTERVAL.key], loops=data[self.LOOPS.key]
                )
        except KeyError:
            return

        if _current_col == loop_col:
            self.DURATION.set_cell_data(
                table, _current_row, duration_col, plan.duration
            )
        elif _current_col == duration_col:
            self.LOOPS.set_cell_data(table, _current_row, loop_col, plan.loops)
        elif _current_col == table.indexOf(self.INTERVAL):
            if self._mode_column == duration_col:
                self.LOOPS.set_cell_data(table, _current_row, loop_col, plan.loops)
            else:
                self.DURATION.set_cell_data(
                    table, _current_row, duration_col, plan.duration
                )

    def _set_mode_column(self, col_idx: int) -> None:
        table = self.table()
        # only duration and loops can be set as active
        if col_idx < table.indexOf(self.DURATION) or not table.columnInfo(col_idx):
            return

        previous, self._mode_column = self._mode_column, col_idx
        if previous != self._mode_column:
            with signals_blocked(self):
                for col in range(table.columnCount()):
                    if header := table.horizontalHeaderItem(col):
                        header.setIcon(icon(MDI6.flag) if col == col_idx else QIcon())
            self._emitting = True
            try:
                self.valueChanged.emit()
            finally:
                self._emitting = False
