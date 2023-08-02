from typing import cast

import pint
import useq

from ._data_table import ColumnMeta, _DataTable


class TimeTable(_DataTable[useq.MultiPhaseTimePlan]):
    """Table for editing a `useq-schema` time plan."""

    PHASE = ColumnMeta(key="phase", checkable=True, default="#{idx}")
    INTERVAL = ColumnMeta(key="interval", type=pint.Quantity, default="1 s")
    DURATION = ColumnMeta(key="duration", type=pint.Quantity, default="1 min")
    LOOPS = ColumnMeta(key="loops", type=int, default=1, minimum=1)

    def value(self, exclude_unchecked: bool = False) -> useq.MultiPhaseTimePlan:
        """Return the current value of the table as a list of channels."""
        phases = [
            {
                "interval": cast("pint.Quantity", p["interval"]).to("s").magnitude,
                "loops": p["loops"],
            }
            for p in super().iterRecords(exclude_unchecked=exclude_unchecked)
        ]

        return useq.MultiPhaseTimePlan(phases=phases)
