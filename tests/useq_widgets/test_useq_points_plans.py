from __future__ import annotations

from typing import TYPE_CHECKING

from useq import GridRowsColumns, OrderMode, RandomPoints

from pymmcore_widgets.useq_widgets import points_plans as pp

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_random_points_widget(qtbot: QtBot) -> None:
    wdg = pp.RandomPointWidget()
    qtbot.addWidget(wdg)
    assert wdg.num_points.value() == 1
    assert wdg.max_width.value() == 0
    assert wdg.max_height.value() == 0
    assert wdg.shape.currentText() == "ellipse"
    assert wdg.random_seed is not None

    points = RandomPoints(
        num_points=5,
        shape="rectangle",
        max_width=100,
        max_height=100,
        fov_height=10,
        fov_width=10,
        random_seed=123,
    )
    with qtbot.waitSignal(wdg.valueChanged):
        wdg.setValue(points)
    assert wdg.value() == points

    assert wdg.num_points.value() == points.num_points
    assert wdg.max_width.value() == points.max_width
    assert wdg.max_height.value() == points.max_height
    assert wdg.shape.currentText() == points.shape.value
    assert wdg.random_seed == points.random_seed


def test_grid_plan_widget(qtbot: QtBot) -> None:
    wdg = pp.GridRowColumnWidget()
    qtbot.addWidget(wdg)
    assert wdg.rows.value() == 1
    assert wdg.columns.value() == 1
    assert wdg.overlap_x.value() == 0
    assert wdg.overlap_y.value() == 0
    assert wdg.mode.currentText() == "row_wise_snake"

    grid = GridRowsColumns(
        rows=5,
        columns=5,
        overlap=(10, 12),
        mode=OrderMode.column_wise_snake,
        fov_height=10,
        fov_width=12,
        relative_to="top_left",
    )
    with qtbot.waitSignal(wdg.valueChanged):
        wdg.setValue(grid)
    assert wdg.value() == grid

    assert wdg.rows.value() == grid.rows
    assert wdg.columns.value() == grid.columns
    assert wdg.overlap_x.value() == grid.overlap[0]
    assert wdg.overlap_y.value() == grid.overlap[1]
    assert wdg.mode.currentText() == grid.mode.value
