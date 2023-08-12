import enum
from pathlib import Path

import pytest
import useq
from pytestqt.qtbot import QtBot

from pymmcore_widgets.useq_widgets import (
    ChannelTable,
    DataTableWidget,
    MDASequenceWidget,
    PositionTable,
    TimeTable,
    ZPlanWidget,
)
from pymmcore_widgets.useq_widgets._column_info import (
    FloatColumn,
    TextColumn,
)


class MyEnum(enum.Enum):
    foo = "bar"
    baz = "qux"


@pytest.mark.parametrize("Wdg", [PositionTable, ChannelTable, TimeTable])
def test_useq_table(qtbot: QtBot, Wdg: type[DataTableWidget]) -> None:
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


def test_z_widget(qtbot: QtBot) -> None:
    wdg = ZPlanWidget()
    qtbot.addWidget(wdg)
    wdg.show()
    wdg.setMode("range_around")
    wdg.range.setValue(4)
    wdg.step.setValue(0.5)
    val = wdg.value()
    assert isinstance(val, useq.ZRangeAround)
    assert val.range == 4
    assert val.step == 0.5


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


SUB_SEQ = useq.MDASequence(
    time_plan=useq.TIntervalLoops(interval=4, loops=4),
    z_plan=useq.ZRangeAround(range=4, step=0.2),
    grid_plan=useq.GridRowsColumns(rows=14, columns=3),
    channels=[{"config": "FITC", "exposure": 32}],
)

MDA = useq.MDASequence(
    time_plan=useq.TIntervalLoops(interval=4, loops=3),
    stage_positions=[(0, 1, 2), useq.Position(x=42, y=0, z=3, sequence=SUB_SEQ)],
    channels=[{"config": "DAPI", "exposure": 42}],
    z_plan=useq.ZRangeAround(range=10, step=0.3),
    grid_plan=useq.GridRowsColumns(rows=10, columns=3),
)


def test_mda_wdg(qtbot: QtBot):
    wdg = MDASequenceWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.setValue(MDA)
    assert wdg.value() == MDA

    wdg.setValue(SUB_SEQ)
    assert wdg.value() == SUB_SEQ


@pytest.mark.parametrize("ext", ["json", "yaml", "foo"])
def test_mda_wdg_load_save(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ext: str
):
    from pymmcore_widgets.useq_widgets._mda_sequence import QFileDialog

    wdg = MDASequenceWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    dest = tmp_path / f"sequence.{ext}"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (dest, None))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: (dest, None))
    dest.write_text("")

    if ext == "foo":
        with pytest.raises(ValueError):
            wdg.load()
        with pytest.raises(ValueError):
            wdg.save()
        return

    dest.write_text(MDA.yaml() if ext == "yaml" else MDA.model_dump_json())

    wdg.load()
    assert wdg.value() == MDA

    wdg.save()
    if ext == "json":
        assert dest.read_text() == MDA.model_dump_json()
    # the yaml dump is correct, but varies from our input because of pydantic set/unset
    # json just includes all fields
