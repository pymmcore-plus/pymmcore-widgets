from __future__ import annotations

import enum
from datetime import timedelta
from typing import TYPE_CHECKING

import pint
import pytest
import useq
from qtpy.QtCore import Qt, QTimer

import pymmcore_widgets
from pymmcore_widgets.useq_widgets import (
    PYMMCW_METADATA_KEY,
    ChannelTable,
    DataTableWidget,
    GridPlanWidget,
    MDASequenceWidget,
    PositionTable,
    TimePlanWidget,
    ZPlanWidget,
    _grid,
    _z,
)
from pymmcore_widgets.useq_widgets._column_info import (
    FloatColumn,
    QTimeLineEdit,
    TextColumn,
    parse_timedelta,
)
from pymmcore_widgets.useq_widgets._positions import MDAButton, QFileDialog, _MDAPopup

if TYPE_CHECKING:
    from pathlib import Path

    from pytestqt.qtbot import QtBot


class MyEnum(enum.Enum):
    foo = "bar"
    baz = "qux"


@pytest.mark.parametrize("Wdg", [PositionTable, ChannelTable, TimePlanWidget])
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
    axis_order="gtcz",
)


MDA = useq.MDASequence(
    time_plan=useq.TIntervalLoops(interval=4, loops=3),
    stage_positions=[(0, 1, 2), useq.Position(x=42, y=0, z=3, sequence=SUB_SEQ)],
    channels=[{"config": "DAPI", "exposure": 42}],
    z_plan=useq.ZRangeAround(range=10, step=0.3),
    grid_plan=useq.GridRowsColumns(rows=10, columns=3),
    axis_order="tpgzc",
    keep_shutter_open_across=("z",),
)


def test_mda_wdg(qtbot: QtBot):
    wdg = MDASequenceWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.setValue(MDA)
    assert wdg.value().replace(metadata={}) == MDA

    wdg.setValue(SUB_SEQ)
    assert wdg.value().replace(metadata={}) == SUB_SEQ


@pytest.mark.parametrize("ext", ["json", "yaml", "foo"])
def test_mda_wdg_load_save(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ext: str
) -> None:
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
    assert wdg.value().replace(metadata={}) == MDA

    wdg.save()
    mda_no_meta = MDA.replace(
        metadata={PYMMCW_METADATA_KEY: {"version": pymmcore_widgets.__version__}}
    )
    if ext == "json":
        assert dest.read_text() == mda_no_meta.model_dump_json(exclude_defaults=True)
    elif ext == "yaml":
        assert dest.read_text() == mda_no_meta.yaml(exclude_defaults=True)


def test_qquant_line_edit(qtbot: QtBot) -> None:
    wdg = QTimeLineEdit("1.0 s")
    wdg.show()
    qtbot.addWidget(wdg)
    wdg.setUreg(pint.UnitRegistry())
    wdg.setFocus()
    with pytest.raises(ValueError):
        wdg.setText("sadsfsd")
    with qtbot.waitSignal(wdg.editingFinished):
        qtbot.keyPress(wdg, Qt.Key.Key_Enter)
    assert not wdg.hasFocus()
    assert wdg.text() == "1.0 s"


def test_position_table(qtbot: QtBot):
    wdg = PositionTable()
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.table().setRowCount(1)
    seq_col = wdg.table().indexOf(wdg.SEQ)
    btn = wdg.table().cellWidget(0, seq_col)

    def handle_dialog():
        popup = btn.findChild(_MDAPopup)
        mda = popup.mda_tabs
        mda.setChecked(mda.indexOf(mda.z_plan), True)
        mda.setChecked(mda.indexOf(mda.channels), True)
        popup.accept()

    QTimer.singleShot(100, handle_dialog)

    with qtbot.waitSignal(wdg.valueChanged):
        btn.seq_btn.click()

    positions = wdg.value()
    assert positions[0].sequence is not None
    assert positions[0].sequence.z_plan is not None
    assert len(positions[0].sequence.channels) == 1


def test_position_table_set_value(qtbot: QtBot) -> None:
    wdg = PositionTable()
    qtbot.addWidget(wdg)
    wdg.show()

    pos = useq.Position(x=1, y=2, z=3, sequence=useq.MDASequence())
    wdg.setValue([pos])

    assert len(wdg.value()) == 1
    # make sure to not set any sub-sequence if the sub-sequence is not None but empty
    seq_btn_idx = wdg.table().indexOf(wdg.SEQ)
    mda_btn = wdg.table().cellWidget(0, seq_btn_idx)
    assert isinstance(mda_btn, MDAButton)
    assert mda_btn.clear_btn.isHidden()

    pos = useq.Position(
        x=1,
        y=2,
        z=3,
        sequence=useq.MDASequence(grid_plan=useq.GridRowsColumns(rows=1, columns=1)),
    )
    wdg.setValue([pos])

    mda_btn = wdg.table().cellWidget(0, seq_btn_idx)
    assert isinstance(mda_btn, MDAButton)
    assert mda_btn.clear_btn.isVisible()


def test_position_load_save(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    wdg = PositionTable()
    qtbot.addWidget(wdg)
    wdg.show()

    dest = tmp_path / "positions.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (dest, None))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: (dest, None))

    wdg.setValue(MDA.stage_positions)
    wdg.save()
    wdg.table().setRowCount(0)
    assert wdg.value() != MDA.stage_positions
    wdg.load()
    assert wdg.value() == MDA.stage_positions


def test_channel_groups(qtbot: QtBot) -> None:
    wdg = ChannelTable()
    qtbot.addWidget(wdg)
    wdg.show()

    GROUPS = {"Channels": ["DAPI", "FITC"], "Other": ["foo", "bar"]}
    wdg.setChannelGroups(GROUPS)

    assert wdg.channelGroups() == GROUPS
    wdg.act_add_row.trigger()
    with qtbot.waitSignal(wdg.valueChanged):
        wdg.act_add_row.trigger()
    val = wdg.value()
    assert val[0].group == "Channels"
    assert val[0].config == "DAPI"
    assert val[1].config == "FITC"

    wdg._group_combo.setCurrentText("Other")
    val = wdg.value()
    assert val[0].group == "Other"
    assert val[0].config == "foo"

    wdg.setChannelGroups(None)

    val = wdg.value()
    assert val[0].group == "Channel"  # default
    assert val[0].config == ""
    assert val[1].config == ""
    with qtbot.waitSignal(wdg.valueChanged):
        wdg.act_add_row.trigger()


def test_time_table(qtbot: QtBot) -> None:
    wdg = TimePlanWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.setValue(useq.TIntervalLoops(interval=0.5, loops=11))
    interval = wdg.table().cellWidget(0, wdg.table().indexOf(wdg.INTERVAL))
    duration = wdg.table().cellWidget(0, wdg.table().indexOf(wdg.DURATION))
    loops = wdg.table().cellWidget(0, wdg.table().indexOf(wdg.LOOPS))
    assert interval.value() == 0.5
    assert duration.value() == 5
    assert loops.value() == 11
    loops.setValue(21)
    assert duration.value() == 10

    # this simulates clicking on the duration column and editing it
    wdg.table().setCurrentCell(0, wdg.table().indexOf(wdg.DURATION))
    duration.setText("20 s")
    duration.textModified.emit("", "")
    assert loops.value() == 41

    wdg.table().setCurrentCell(0, wdg.table().indexOf(wdg.INTERVAL))
    interval.setText("1 s")
    interval.textModified.emit("", "")
    assert duration.value() == 20
    assert loops.value() == 21

    wdg.setValue(None)
    assert wdg.table().rowCount() == 0


def test_z_plan_widget(qtbot: QtBot) -> None:
    wdg = ZPlanWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.setMode("top_bottom")

    assert wdg.mode() == _z.Mode.TOP_BOTTOM
    assert wdg.top.isVisible()
    assert not wdg.above.isVisible()
    wdg._mode_range.trigger()
    assert wdg.range.isVisible()
    assert not wdg.top.isVisible()
    wdg._mode_above_below.trigger()
    assert wdg.above.isVisible()
    assert not wdg.range.isVisible()

    assert wdg.step.value() == 1
    wdg.setSuggestedStep(0.5)
    assert wdg.suggestedStep() == 0.5
    wdg.useSuggestedStep()
    assert wdg.step.value() == 0.5

    assert wdg.isGoUp()
    wdg.setGoUp(False)
    assert wdg._top_to_bottom.isChecked()
    assert not wdg.isGoUp()

    plan = useq.ZTopBottom(top=1, bottom=2, step=0.2)
    wdg.setValue(plan)
    assert wdg.value() == plan
    assert wdg.top.isVisible()

    plan = useq.ZRangeAround(range=4, step=0.2)
    wdg.setValue(plan)
    assert wdg.value() == plan
    assert not wdg.above.isVisible()

    plan = useq.ZAboveBelow(above=1, below=2, step=0.2)
    wdg.setValue(plan)
    assert wdg.value() == plan
    assert wdg.above.isVisible()

    assert wdg.currentZRange() == plan.above + plan.below

    assert wdg.steps.value() == 16
    with qtbot.waitSignal(wdg.valueChanged):
        wdg.steps.setValue(6)
    assert wdg.steps.value() == 6
    assert wdg.value().step == 0.5

    with pytest.raises(TypeError):
        plan = useq.ZAbsolutePositions(absolute=[1, 2, 3])
        wdg.setValue(plan)


def test_grid_plan_widget(qtbot: QtBot) -> None:
    wdg = GridPlanWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.setMode("bounds")
    assert isinstance(wdg.value(), useq.GridFromEdges)
    wdg.setMode("number")
    assert isinstance(wdg.value(), useq.GridRowsColumns)
    wdg.setMode("area")
    assert isinstance(wdg.value(), useq.GridWidthHeight)

    plan = useq.GridRowsColumns(rows=3, columns=3, mode="spiral", overlap=10)
    with qtbot.waitSignal(wdg.valueChanged):
        wdg.setValue(plan)
    assert wdg.mode() == _grid.Mode.NUMBER
    assert wdg.value() == plan

    plan = useq.GridFromEdges(left=1, right=2, top=3, bottom=4, overlap=10)
    with qtbot.waitSignal(wdg.valueChanged):
        wdg.setValue(plan)
    assert wdg.mode() == _grid.Mode.BOUNDS
    assert wdg.value() == plan

    plan = useq.GridWidthHeight(width=1000, height=2000, fov_height=3, fov_width=4)
    with qtbot.waitSignal(wdg.valueChanged):
        wdg.setValue(plan)
    assert wdg.mode() == _grid.Mode.AREA
    assert wdg.value() == plan

    assert wdg._fov_height == 3
    wdg.setFovHeight(5)
    assert wdg.fovHeight() == 5

    assert wdg._fov_width == 4
    wdg.setFovWidth(6)
    assert wdg.fovWidth() == 6


def test_proper_checked_index(qtbot) -> None:
    """Testing that the proper tab is checked when setting a value

    https://github.com/pymmcore-plus/pymmcore-widgets/issues/205
    """
    import useq

    from pymmcore_widgets.useq_widgets._positions import _MDAPopup

    seq = useq.MDASequence(grid_plan=useq.GridRowsColumns(rows=2, columns=3))
    pop = _MDAPopup(seq)
    qtbot.addWidget(pop)
    assert pop.mda_tabs.grid_plan.isEnabled()
    assert pop.mda_tabs.isChecked(pop.mda_tabs.grid_plan)


MDA = useq.MDASequence(axis_order="p", stage_positions=[(0, 1, 2)])
AF = useq.MDASequence(
    autofocus_plan=useq.AxesBasedAF(autofocus_motor_offset=10.0, axes=("p",))
)
AF1 = useq.MDASequence(
    autofocus_plan=useq.AxesBasedAF(autofocus_motor_offset=20.0, axes=("p",))
)


def test_mda_wdg_with_autofocus(qtbot: QtBot) -> None:
    wdg = MDASequenceWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.setValue(MDA)
    assert wdg.value().replace(metadata={}) == MDA

    MDA1 = MDA.replace(
        stage_positions=[
            useq.Position(x=0, y=1, z=2, sequence=AF),
            useq.Position(x=0, y=1, z=2, sequence=AF1),
        ]
    )
    wdg.setValue(MDA1)
    assert wdg.value().replace(metadata={}) == MDA1

    MDA2 = MDA.replace(
        stage_positions=[
            useq.Position(x=0, y=1, z=2, sequence=AF),
            useq.Position(x=0, y=1, z=2, sequence=AF),
        ]
    )
    wdg.setValue(MDA2)
    assert wdg.value().autofocus_plan
    assert not wdg.value().stage_positions[0].sequence
    assert not wdg.value().stage_positions[1].sequence


def test_parse_time() -> None:
    assert parse_timedelta("2") == timedelta(seconds=2)
    assert parse_timedelta("0.5") == timedelta(seconds=0.5)
    assert parse_timedelta("0.500") == timedelta(seconds=0.5)
    assert parse_timedelta("0.75") == timedelta(seconds=0.75)
    # this syntax still fails... it assumes the 2 is hours, and the 30 is seconds...
    # assert parse_timedelta("2:30") == timedelta(minutes=2, seconds=30)
    assert parse_timedelta("1:20:15") == timedelta(hours=1, minutes=20, seconds=15)
    assert parse_timedelta("0:00:00.500000") == timedelta(seconds=0.5)
    assert parse_timedelta("3:40:10.500") == timedelta(
        hours=3, minutes=40, seconds=10.5
    )
