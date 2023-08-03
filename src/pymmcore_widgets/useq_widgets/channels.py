import useq

from ._data_table import ColumnMeta, _DataTable


class ChannelTable(_DataTable):
    """Table for editing a list of `useq.Channels`."""

    GROUP = ColumnMeta(key="group", default="Channel", hidden=True)
    CONFIG = ColumnMeta(key="config", checkable=True, default="#{idx}")
    EXPOSURE = ColumnMeta(
        key="exposure", header="Exposure [ms]", default=100, minimum=1
    )
    ACUIRE_EVERY = ColumnMeta(key="acquire_every", type=int, default=1, minimum=1)
    DO_STACK = ColumnMeta(key="do_stack", type=bool, default=True)
    Z_OFFSET = ColumnMeta(
        key="z_offset", type=float, default=0.0, minimum=-10000, maximum=10000
    )

    def value(self, exclude_unchecked: bool = False) -> list[useq.Channel]:
        """Return the current value of the table as a list of channels."""
        return [
            useq.Channel(**r)
            for r in self.iterRecords(exclude_unchecked=exclude_unchecked)
        ]
