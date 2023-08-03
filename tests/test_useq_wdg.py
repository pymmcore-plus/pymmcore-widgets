import enum

import pytest
from pytestqt.qtbot import QtBot

from pymmcore_widgets.useq_widgets import (
    ChannelTable,
    DataTableWidget,
    MDASequenceWidget,
    PositionTable,
    TimeTable,
)
from pymmcore_widgets.useq_widgets._column_info import (
    FloatColumn,
    TextColumn,
)


class MyEnum(enum.Enum):
    foo = "bar"
    baz = "qux"


@pytest.mark.parametrize("Wdg", [PositionTable, ChannelTable, TimeTable])
def test_useq_wdg(qtbot: QtBot, Wdg: type[DataTableWidget]) -> None:
    wdg = Wdg()
    qtbot.addWidget(wdg)
    table = wdg.table()
    table.setRowCount(2)
    wdg.show()

    assert wdg.toolBar()  # public attr
    for col in Wdg.COLUMNS:
        assert table.indexOf(col) == table.indexOf(col.header_text()) >= 0
        assert list(wdg.value(exclude_unchecked=False))
        assert list(wdg.value(exclude_unchecked=True))

    assert table.indexOf("foo") == -1


def test_data_table(qtbot: QtBot) -> None:
    wdg = DataTableWidget()
    qtbot.addWidget(wdg)
    table = wdg.table()
    table.setRowCount(2)
    for col_meta in [
        TextColumn(key="foo", default="bar", is_row_selector=True),
        TextColumn(key="baz", default="qux"),
        FloatColumn(key="qux", default=42.0),
    ]:
        table.addColumn(col_meta, position=-1)

    table.setRowCount(4)
    assert list(wdg.value(exclude_unchecked=False))

    n_rows = table.rowCount()
    wdg.act_add_row.trigger()
    assert table.rowCount() == n_rows + 1
    table.selectRow(table.rowCount() - 1)
    wdg.act_remove_row.trigger()
    assert table.rowCount() == n_rows
    wdg.act_check_all.trigger()
    assert len(wdg.value()) == table.rowCount()
    wdg.act_check_none.trigger()
    assert len(wdg.value()) == 0  # requires a is_row_selector=True column
    wdg.act_clear.trigger()
    assert table.rowCount() == 0


def test_mda_wdg(qtbot: QtBot):
    wdg = MDASequenceWidget()
    qtbot.addWidget(wdg)
    wdg.show()
