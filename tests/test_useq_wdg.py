import enum

import pytest
from pytestqt.qtbot import QtBot

from pymmcore_widgets.useq_widgets import (
    ChannelTable,
    ColumnMeta,
    MDASequenceWidget,
    PositionTable,
    TimeTable,
)
from pymmcore_widgets.useq_widgets._data_table import DataTable


class MyEnum(enum.Enum):
    foo = "bar"
    baz = "qux"


@pytest.mark.parametrize("Wdg", [PositionTable, ChannelTable, TimeTable])
def test_useq_wdg(qtbot: QtBot, Wdg: type[DataTable]) -> None:
    wdg = Wdg()
    qtbot.addWidget(wdg)
    wdg.table.setRowCount(2)
    wdg.show()

    assert wdg.table  # public attr
    assert wdg.toolbar  # public attr
    for col in Wdg.COLUMNS:
        assert wdg.indexOf(col) == wdg.indexOf(col.header_text()) >= 0
        assert list(wdg.value(exclude_unchecked=False))
        assert list(wdg.value(exclude_unchecked=True))

    assert wdg.indexOf("foo") == -1


def test_data_table(qtbot: QtBot) -> None:
    wdg = DataTable()
    qtbot.addWidget(wdg)
    wdg.table.setRowCount(2)
    for col_meta in (
        columns := [
            ColumnMeta(key="foo", default="bar"),
            ColumnMeta(key="baz", type=MyEnum, default=MyEnum.foo),
            ColumnMeta(key="qux", type=float, default=42.0),
        ]
    ):
        wdg.addColumn(col_meta, position=-1)

    wdg.table.setRowCount(4)
    assert list(wdg.value(exclude_unchecked=False))

    n_rows = wdg.rowCount()
    wdg.act_add_row.trigger()
    assert wdg.rowCount() == n_rows + 1
    wdg.table.selectRow(wdg.rowCount() - 1)
    wdg.act_remove_row.trigger()
    assert wdg.rowCount() == n_rows
    wdg.act_select_all.trigger()
    assert wdg._selected_rows() == sorted(range(wdg.rowCount()))
    wdg.act_select_none.trigger()
    assert wdg._selected_rows() == []
    wdg.act_clear.trigger()
    assert wdg.rowCount() == 0


def test_mda_wdg(qtbot: QtBot):
    wdg = MDASequenceWidget()
    qtbot.addWidget(wdg)
    wdg.show()
