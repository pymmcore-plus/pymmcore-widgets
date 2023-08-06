from typing import Sequence

import useq

from ._column_info import FloatColumn, TextColumn
from ._data_table import DataTableWidget


class PositionTable(DataTableWidget):
    """Table for editing a list of `useq.Positions`."""

    POSITION = TextColumn(key="name", default="#{idx}", is_row_selector=True)
    X = FloatColumn(key="x", header="X [mm]", default=0.0)
    Y = FloatColumn(key="y", header="Y [mm]", default=0.0)
    Z = FloatColumn(key="z", header="Z [mm]", default=0.0)

    def value(self, exclude_unchecked: bool = True) -> list[useq.Position]:
        """Return the current value of the table as a list of channels."""
        return [
            useq.Position(**r)
            for r in self.table().iterRecords(exclude_unchecked=exclude_unchecked)
        ]

    def setValue(self, value: Sequence[useq.Position]) -> None:
        """Set the current value of the table."""
        _values = []
        for v in value:
            if not isinstance(v, useq.Position):
                raise TypeError(f"Expected useq.Position, got {type(v)}")
            _values.append(v.model_dump(exclude_unset=True))
        super().setValue(_values)
