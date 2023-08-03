import useq

from ._data_table import ColumnMeta, _DataTable


class PositionTable(_DataTable):
    """Table for editing a list of `useq.Positions`."""

    POSITION = ColumnMeta(key="name", checkable=True, default="#{idx}")
    X = ColumnMeta(key="x", header="X [mm]", type=float, default=0.0)
    Y = ColumnMeta(key="y", header="Y [mm]", type=float, default=0.0)
    Z = ColumnMeta(key="z", header="Z [mm]", type=float, default=0.0)

    def value(self, exclude_unchecked: bool = False) -> list[useq.Position]:
        """Return the current value of the table as a list of channels."""
        return [
            useq.Position(**r)
            for r in super().iterRecords(exclude_unchecked=exclude_unchecked)
        ]
