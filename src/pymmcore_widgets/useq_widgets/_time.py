import useq

from ._column_info import IntColumn, TextColumn, TimeDeltaColumn
from ._data_table import DataTableWidget


class TimeTable(DataTableWidget):
    """Table for editing a `useq-schema` time plan."""

    PHASE = TextColumn(key="phase", default="#{idx}", is_row_selector=True)
    INTERVAL = TimeDeltaColumn(key="interval", default="1 s")
    DURATION = TimeDeltaColumn(key="duration", default="1 min")
    LOOPS = IntColumn(key="loops", default=1, minimum=1)

    def value(self, exclude_unchecked: bool = True) -> useq.MultiPhaseTimePlan:
        """Return the current value of the table as a list of channels."""
        phases = [
            {"interval": p["interval"], "loops": p["loops"]}
            for p in self.table().iterRecords(exclude_unchecked=exclude_unchecked)
        ]

        return useq.MultiPhaseTimePlan(phases=phases)

    def setValue(
        self,
        value: useq.MultiPhaseTimePlan
        | useq.TDurationLoops
        | useq.TIntervalLoops
        | useq.TIntervalDuration,
    ) -> None:
        """Set the current value of the table."""
        if isinstance(value, useq.MultiPhaseTimePlan):
            _phases = value.phases
        elif isinstance(
            value, (useq.TDurationLoops, useq.TIntervalLoops, useq.TIntervalDuration)
        ):
            _phases = [value]
        else:
            raise TypeError(
                f"Expected useq.MultiPhaseTimePlan, got {type(value)} instead."
            )
        super().setValue([p.model_dump(exclude_unset=True) for p in _phases])
