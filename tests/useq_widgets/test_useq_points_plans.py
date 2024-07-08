from __future__ import annotations

from typing import TYPE_CHECKING

from useq import GridRowsColumns, OrderMode, RandomPoints, RelativePosition

from pymmcore_widgets.useq_widgets import points_plans as pp

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

RANDOM_POINTS = RandomPoints(
    num_points=5,
    shape="rectangle",
    max_width=100,
    max_height=100,
    fov_height=10,
    fov_width=10,
    random_seed=123,
    allow_overlap=True,
)

GRID_ROWS_COLS = GridRowsColumns(
    rows=5,
    columns=5,
    overlap=(10, 12),
    mode=OrderMode.column_wise_snake,
    fov_height=10,
    fov_width=12,
    relative_to="top_left",
)


def test_random_points_widget(qtbot: QtBot) -> None:
    wdg = pp.RandomPointWidget()
    qtbot.addWidget(wdg)
    assert wdg.num_points.value() == 1
    assert wdg.max_width.value() == 0
    assert wdg.max_height.value() == 0
    assert wdg.shape.currentText() == "ellipse"
    assert not wdg.allow_overlap.isChecked()
    assert wdg.random_seed is not None

    with qtbot.waitSignal(wdg.valueChanged):
        wdg.setValue(RANDOM_POINTS)
    assert wdg.value() == RANDOM_POINTS

    assert wdg.num_points.value() == RANDOM_POINTS.num_points
    assert wdg.max_width.value() == RANDOM_POINTS.max_width
    assert wdg.max_height.value() == RANDOM_POINTS.max_height
    assert wdg.shape.currentText() == RANDOM_POINTS.shape.value
    assert wdg.random_seed == RANDOM_POINTS.random_seed
    assert wdg.allow_overlap.isChecked() == RANDOM_POINTS.allow_overlap


def test_grid_plan_widget(qtbot: QtBot) -> None:
    wdg = pp.GridRowColumnWidget()
    qtbot.addWidget(wdg)
    assert wdg.rows.value() == 1
    assert wdg.columns.value() == 1
    assert wdg.overlap_x.value() == 0
    assert wdg.overlap_y.value() == 0
    assert wdg.mode.currentText() == "row_wise_snake"

    with qtbot.waitSignal(wdg.valueChanged):
        wdg.setValue(GRID_ROWS_COLS)
    assert wdg.value() == GRID_ROWS_COLS

    assert wdg.rows.value() == GRID_ROWS_COLS.rows
    assert wdg.columns.value() == GRID_ROWS_COLS.columns
    assert wdg.overlap_x.value() == GRID_ROWS_COLS.overlap[0]
    assert wdg.overlap_y.value() == GRID_ROWS_COLS.overlap[1]
    assert wdg.mode.currentText() == GRID_ROWS_COLS.mode.value


def test_point_plan_selector(qtbot: QtBot) -> None:
    wdg = pp.RelativePointPlanSelector()
    qtbot.addWidget(wdg)

    assert isinstance(wdg.value(), RelativePosition)

    wdg.setValue(RANDOM_POINTS)
    assert wdg.value() == RANDOM_POINTS
    assert wdg.random_radio_btn.isChecked()

    wdg.setValue(GRID_ROWS_COLS)
    assert wdg.value() == GRID_ROWS_COLS
    assert wdg.grid_radio_btn.isChecked()

    wdg.random_radio_btn.setChecked(True)
    assert wdg.value() == RANDOM_POINTS
