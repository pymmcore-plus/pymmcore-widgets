from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Mapping, Sequence

import useq
from qtpy.QtWidgets import QComboBox, QWidgetAction
from superqt.utils import signals_blocked

from ._column_info import (
    BoolColumn,
    ChoiceColumn,
    ColumnInfo,
    FloatColumn,
    IntColumn,
    TextColumn,
)
from ._data_table import DataTableWidget

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

NAMED_CONFIG = TextColumn(key="config", default=None, is_row_selector=True)


class ChannelTable(DataTableWidget):
    """Table for editing a list of `useq.Channels`."""

    # fmt: off
    GROUP = TextColumn(key="group", default="Channel", hidden=True)
    CONFIG = TextColumn(key="config", default=None, is_row_selector=True)
    EXPOSURE = FloatColumn(key="exposure", header="Exposure [ms]", default=100.0, minimum=1)  # noqa
    ACQUIRE_EVERY = IntColumn(key="acquire_every", default=1, minimum=1)
    DO_STACK = BoolColumn(key="do_stack", default=True)
    Z_OFFSET = FloatColumn(key="z_offset", default=0.0, minimum=-10000, maximum=10000)
    # fmt: on
    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, parent)
        self._group_combo = QComboBox()
        self._group_combo.currentTextChanged.connect(self._on_group_changed)
        self._groups: Mapping[str, Sequence[str]] = {}

    def setChannelGroups(self, groups: Mapping[str, Sequence[str]] | None) -> None:
        """Set the groups that can be selected in the table.

        Parameters
        ----------
        groups : Mapping[str, Sequence[str]]
            A mapping of group names to a sequence of config names.
            {'Channel': ['DAPI', 'FITC']}
        """
        # store new groups
        groups = groups or {}
        self._groups, ngroups_before = groups, len(self._groups)

        # update the group combo
        with signals_blocked(self._group_combo):
            self._group_combo.clear()
            for group_name in groups:
                self._group_combo.addItem(group_name)

        # update the to show the combobox if there are more than one group
        toolbar = self.toolBar()
        actions = [x for x in toolbar.children() if isinstance(x, QWidgetAction)]
        if len(self._groups) <= 1:
            if ngroups_before > 1:
                toolbar.removeAction(actions[1])
        else:
            toolbar.insertWidget(actions[0], self._group_combo)

        self._on_group_changed()

    def channelGroups(self) -> Mapping[str, Sequence[str]]:
        return self._groups

    def value(self, exclude_unchecked: bool = True) -> tuple[useq.Channel, ...]:
        """Return the current value of the table as a list of channels."""
        return tuple(
            useq.Channel(**r)
            for r in self.table().iterRecords(exclude_unchecked=exclude_unchecked)
        )

    def setValue(self, value: Iterable[useq.Channel]) -> None:
        """Set the current value of the table."""
        _values = []
        for v in value:
            if not isinstance(v, useq.Channel):  # pragma: no cover
                raise TypeError(f"Expected useq.Channel, got {type(v)}")
            _values.append(v.model_dump(exclude_unset=True))
        super().setValue(_values)

    def _on_group_changed(self) -> None:
        group = self._group_combo.currentText()
        table = self.table()
        group_col = 1
        for i in range(table.rowCount()):
            if item := table.item(i, group_col):
                item.setText(group)

        table = self.table()
        table.removeColumn(group_col)
        if group and (config_names := self._groups[group]):
            col: ColumnInfo = ChoiceColumn(
                key="config",
                default=config_names[0],
                is_row_selector=True,
                allowed_values=tuple(config_names),
            )
        else:
            col = self.CONFIG
        table.addColumn(col, group_col)
