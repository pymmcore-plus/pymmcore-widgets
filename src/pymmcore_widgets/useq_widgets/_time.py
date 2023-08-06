from typing import Any

import useq
from fonticon_mdi6 import MDI6
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QWidget
from superqt.fonticon import icon

from ._column_info import IntColumn, TextColumn, TimeDeltaColumn
from ._data_table import DataTableWidget


class TimeTable(DataTableWidget):
    """Table for editing a `useq-schema` time plan."""

    PHASE = TextColumn(key="phase", default="#{idx}", is_row_selector=True)
    INTERVAL = TimeDeltaColumn(key="interval", default="1 s")
    DURATION = TimeDeltaColumn(key="duration", default="0 s")
    LOOPS = IntColumn(key="loops", default=1, minimum=1)

    _active_column: str

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, parent)

        h_header = self.table().horizontalHeader()
        h_header.setSectionsClickable(True)
        h_header.sectionClicked.connect(self._set_active_column)

        self._set_active_column(self.table().indexOf(self.LOOPS))

    def _set_active_column(self, col_idx: int) -> None:
        table = self.table()
        # only duration and loops can be set as active
        if col_idx < table.indexOf(self.DURATION):
            return
        if not (_info := table.columnInfo(col_idx)):
            return

        previous, self._active_column = getattr(self, "_active_column", None), _info.key
        for col in range(table.columnCount()):
            if header := table.horizontalHeaderItem(col):
                _icon = icon(MDI6.flag) if col == col_idx else QIcon()
                header.setIcon(_icon)
        if previous != self._active_column:
            self.valueChanged.emit()

    def value(self, exclude_unchecked: bool = True) -> useq.MultiPhaseTimePlan:
        """Return the current value of the table as a list of channels."""
        active_key = "duration" if self._active_column == self.DURATION.key else "loops"
        phases = [
            {"interval": p["interval"], active_key: p[active_key]}
            for p in self.table().iterRecords(exclude_unchecked=exclude_unchecked)
        ]
        return useq.MultiPhaseTimePlan(phases=phases)

    def setValue(self, value: Any) -> None:
        """Set the current value of the table."""
        if isinstance(value, useq.MultiPhaseTimePlan):
            _phases = value.phases
        elif isinstance(
            value, (useq.TDurationLoops, useq.TIntervalLoops, useq.TIntervalDuration)
        ):
            _phases = [value]
        else:
            raise TypeError(f"Expected useq TimePlan, got {type(value)}.")
        super().setValue([p.model_dump(exclude_unset=True) for p in _phases])

        if isinstance(value, (useq.TIntervalDuration)):
            self._set_active_column(self.table().indexOf(self.DURATION))
        else:
            self._set_active_column(self.table().indexOf(self.LOOPS))
