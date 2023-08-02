import useq

from ._data_table import ColumnMeta, _DataTable


class ChannelTable(_DataTable):
    """Table for editing a list of `useq.Channels`."""

    GROUP = ColumnMeta(key="group", default="Channel", hidden=True)
    CONFIG = ColumnMeta(key="config", checkable=True, default="#{idx}")
    T_POS = ColumnMeta(key="acquire_every", type=int, default=1, minimum=1)
    DO_Z = ColumnMeta(key="do_stack", type=bool, default=True)

    def value(self, exclude_unchecked: bool = False) -> list[useq.Channel]:
        """Return the current value of the table as a list of channels."""
        return [
            useq.Channel(**r)
            for r in super().iterRecords(exclude_unchecked=exclude_unchecked)
        ]
