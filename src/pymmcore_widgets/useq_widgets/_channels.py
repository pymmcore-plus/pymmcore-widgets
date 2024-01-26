from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping, Sequence

import useq
from pymmcore_plus import Keyword
from qtpy.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget, QWidgetAction
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

NAMED_CONFIG = TextColumn(key="config", default=None, is_row_selector=True)
DEFAULT_GROUP = Keyword.Channel


class ChannelTable(DataTableWidget):
    """Table to edit a list of [useq.Channels](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Channel)."""

    # fmt: off
    GROUP = TextColumn(key="group", default=DEFAULT_GROUP, hidden=True)
    CONFIG = TextColumn(key="config", default=None, is_row_selector=True)
    EXPOSURE = FloatColumn(key="exposure", header="Exposure [ms]", default=100.0, minimum=0.01)  # noqa
    ACQUIRE_EVERY = IntColumn(key="acquire_every", default=1, minimum=1)
    DO_STACK = BoolColumn(key="do_stack", default=True)
    Z_OFFSET = FloatColumn(key="z_offset", default=0.0, minimum=-10000, maximum=10000)
    # fmt: on
    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, parent)
        self._group_combo = QComboBox()
        self._group_combo.currentTextChanged.connect(self._on_group_changed)

        self._group_wdg = QWidget()
        layout = QHBoxLayout(self._group_wdg)
        layout.addWidget(QLabel("Group:"))
        layout.addWidget(self._group_combo)
        layout.addStretch()
        layout.setContentsMargins(5, 0, 0, 0)

        # These will change in on_group_changed... so we store the current values.
        self._groups: Mapping[str, Sequence[str]] = {}
        self._config_column: ColumnInfo = self.CONFIG

        # when a new row is inserted, call _on_rows_inserted
        # to update the new values from the _group_combo
        self.table().model().rowsInserted.connect(self._on_rows_inserted)

    def setChannelGroups(self, groups: Mapping[str, Sequence[str]] | None) -> None:
        """Set the channel groups that can be selected in the table.

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
        elif ngroups_before <= 1:
            self._group_wdg.show()
            toolbar.insertWidget(actions[0], self._group_wdg)

        self._on_group_changed()

    def channelGroups(self) -> Mapping[str, Sequence[str]]:
        """Return the current channel groups that can be selected in the table."""
        return self._groups

    def value(self, exclude_unchecked: bool = True) -> tuple[useq.Channel, ...]:
        """Return the current value of the table as a tuple of [useq.Channels](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Channel).

        Parameters
        ----------
        exclude_unchecked : bool, optional
            Exclude unchecked rows, by default True

        Returns
        -------
        tuple[useq.Channel, ...]
            A tuple of [useq.Channels](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Channel).
        """
        return tuple(
            useq.Channel(**r)
            for r in self.table().iterRecords(exclude_unchecked=exclude_unchecked)
        )

    def setValue(self, value: Iterable[useq.Channel]) -> None:
        """Set the current value of the table from an Iterable of [useq.Channels](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Channel).

        Parameters
        ----------
        value : Iterable[useq.Channel]
            An Iterable of [useq.Channels](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Channel).
        """
        _values = []
        for v in value:
            if not isinstance(v, useq.Channel):  # pragma: no cover
                raise TypeError(f"Expected useq.Channel, got {type(v)}")
            _values.append(v.model_dump(exclude_unset=True))
        super().setValue(_values)

    # ------------------- Private API -------------------

    def _on_group_changed(self) -> None:
        group = self._group_combo.currentText()
        table = self.table()

        # set the group column values
        group_col = self.table().indexOf(self.GROUP)
        for i in range(table.rowCount()):
            if item := table.item(i, group_col):
                item.setText(group or DEFAULT_GROUP)

        # Change the config column to a choice column with the current group's values
        # or back to the default config column if there are no groups.
        config_col = self.table().indexOf(self._config_column)
        table.removeColumn(config_col)
        if group and (config_names := self._groups[group]):
            self._config_column = ChoiceColumn(
                key="config",
                default=config_names[0],
                is_row_selector=True,
                allowed_values=tuple(config_names),
            )
        else:
            self._config_column = self.CONFIG
        table.addColumn(self._config_column, config_col)

    def _add_row(self) -> None:
        """Add a new to the end of the table.

        Selecting the next unused config name.
        """
        if not self._groups:
            # there's nothing to choose from, so just add a row
            super()._add_row()
            return

        # get all current values
        table = self.table()
        col = table.indexOf(self._config_column)
        counts = Counter(
            next(iter(self._config_column.get_cell_data(table, row, col).values()))
            for row in range(table.rowCount())
        )
        # make sure everything is in there at least once
        counts.update(reversed(self._groups[self._group_combo.currentText()]))

        with signals_blocked(self):
            super()._add_row()
            # set the new config name to the least common one
            self._config_column.set_cell_data(
                table, table.rowCount() - 1, col, counts.most_common()[-1][0]
            )

        self.valueChanged.emit()

    def _on_rows_inserted(self, parent: Any, start: int, end: int) -> None:
        # when a new row is inserted by any means, populate it
        # this is connected above in __init_ with self.model().rowsInserted.connect
        with signals_blocked(self):
            for row_idx in range(start, end + 1):
                self._set_channel_group_from_combo(row_idx)
        self.valueChanged.emit()

    def _set_channel_group_from_combo(self, row: int, col: int = 0) -> None:
        """Set the current channel group form the combo at the given row."""
        group = self._group_combo.currentText()
        if not group:
            return

        data = {self.GROUP.key: group}
        self.table().setRowData(row, data)
