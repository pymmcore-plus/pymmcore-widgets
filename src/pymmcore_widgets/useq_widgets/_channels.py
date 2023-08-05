import useq

from ._column_info import BoolColumn, FloatColumn, IntColumn, TextColumn
from ._data_table import DataTableWidget


class ChannelTable(DataTableWidget):
    """Table for editing a list of `useq.Channels`."""

    # fmt: off
    GROUP = TextColumn(key="group", default="Channel", hidden=True)
    CONFIG = TextColumn(key="config", default="#{idx}", checkable=True, is_row_selector=True)  # noqa
    EXPOSURE = FloatColumn(key="exposure", header="Exposure [ms]", default=100.0, minimum=1)  # noqa
    ACUIRE_EVERY = IntColumn(key="acquire_every", default=1, minimum=1)
    DO_STACK = BoolColumn(key="do_stack", default=True)
    Z_OFFSET = FloatColumn(key="z_offset", default=0.0, minimum=-10000, maximum=10000)
    # fmt: on

    def value(self, exclude_unchecked: bool = False) -> list[useq.Channel]:
        """Return the current value of the table as a list of channels."""
        return [
            useq.Channel(**r)
            for r in self.table().iterRecords(exclude_unchecked=exclude_unchecked)
        ]
