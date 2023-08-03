import useq

from ._column_info import IntColumn, TextColumn, TimeDeltaColumn
from ._data_table import DataTableWidget


class TimeTable(DataTableWidget):
    """Table for editing a `useq-schema` time plan."""

    PHASE = TextColumn(key="phase", checkable=True, default="#{idx}")
    INTERVAL = TimeDeltaColumn(key="interval", default="1 s")
    DURATION = TimeDeltaColumn(key="duration", default="1 min")
    LOOPS = IntColumn(key="loops", default=1, minimum=1)

    def value(self, exclude_unchecked: bool = False) -> useq.MultiPhaseTimePlan:
        """Return the current value of the table as a list of channels."""
        phases = [
            {"interval": p["interval"], "loops": p["loops"]}
            for p in self.table().iterRecords(exclude_unchecked=exclude_unchecked)
        ]

        return useq.MultiPhaseTimePlan(phases=phases)
