from typing import Iterable

import useq

from ._column_info import BoolColumn, FloatColumn, IntColumn, TextColumn
from ._data_table import DataTableWidget


class ChannelTable(DataTableWidget):
    """Table for editing a list of `useq.Channels`."""

    # fmt: off
    GROUP = TextColumn(key="group", default="Channel", hidden=True)
    CONFIG = TextColumn(key="config", default=None, is_row_selector=True)
    EXPOSURE = FloatColumn(key="exposure", header="Exposure [ms]", default=100.0, minimum=1)  # noqa
    ACUIRE_EVERY = IntColumn(key="acquire_every", default=1, minimum=1)
    DO_STACK = BoolColumn(key="do_stack", default=True)
    Z_OFFSET = FloatColumn(key="z_offset", default=0.0, minimum=-10000, maximum=10000)
    # fmt: on

    def value(self, exclude_unchecked: bool = True) -> list[useq.Channel]:
        """Return the current value of the table as a list of channels."""
        return [
            useq.Channel(**r)
            for r in self.table().iterRecords(exclude_unchecked=exclude_unchecked)
        ]

    def setValue(self, value: Iterable[useq.Channel]) -> None:
        """Set the current value of the table."""
        _values = []
        for v in value:
            if not isinstance(v, useq.Channel):  # pragma: no cover
                raise TypeError(f"Expected useq.Channel, got {type(v)}")
            _values.append(v.model_dump(exclude_unset=True))
        super().setValue(_values)
