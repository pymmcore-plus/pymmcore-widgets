from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import qtpy
import useq
from qtpy.QtCore import Qt
from qtpy.QtGui import QMouseEvent
from useq import GridRowsColumns, OrderMode, RandomPoints, RelativePosition, Shape

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
    order="random",
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

RELATIVE_POSITION = RelativePosition()


def test_random_points_widget(qtbot: QtBot) -> None:
    wdg = pp.RandomPointWidget()
    qtbot.addWidget(wdg)
    assert wdg.num_points.value() == 1
    assert wdg.max_width.value() == 1000
    assert wdg.max_height.value() == 1000
    assert wdg.shape.currentText() == "ellipse"
    assert not wdg.allow_overlap.isChecked()
    assert wdg.order.currentText() == "two_opt"
    assert wdg.random_seed is not None

    with qtbot.waitSignal(wdg.valueChanged):
        wdg.setValue(RANDOM_POINTS)
    assert wdg.value() == RANDOM_POINTS

    assert wdg.num_points.value() == RANDOM_POINTS.num_points
    assert wdg.max_width.value() == RANDOM_POINTS.max_width
    assert wdg.max_height.value() == RANDOM_POINTS.max_height
    assert wdg.shape.currentText() == RANDOM_POINTS.shape.value
    assert wdg.random_seed == RANDOM_POINTS.random_seed
    assert wdg.order.currentText() == RANDOM_POINTS.order.value
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

    wdg.setValue(RELATIVE_POSITION)
    assert wdg.value() == RELATIVE_POSITION
    assert wdg.single_radio_btn.isChecked()

    wdg.setValue(GRID_ROWS_COLS)
    assert wdg.value() == GRID_ROWS_COLS
    assert wdg.grid_radio_btn.isChecked()

    wdg.random_radio_btn.setChecked(True)
    # fov_width and fov_height are global to the RelativePointPlanSelector
    # so setting the value to GRID_ROWS_COLS will update the fov_width and fov_height
    assert wdg.value() == RANDOM_POINTS.model_copy(
        update={
            "fov_width": GRID_ROWS_COLS.fov_width,
            "fov_height": GRID_ROWS_COLS.fov_height,
        }
    )


def test_points_plan_widget(qtbot: QtBot) -> None:
    """PointsPlanWidget is a RelativePointPlanSelector combined with a graphics view."""
    wdg = pp.PointsPlanWidget()
    wdg.show()
    qtbot.addWidget(wdg)

    for plan in (RANDOM_POINTS, RELATIVE_POSITION, GRID_ROWS_COLS):
        with qtbot.waitSignal(wdg.valueChanged):
            wdg.setValue(plan)
        assert wdg.value() == plan


@pytest.mark.parametrize(
    "plan",
    [
        RELATIVE_POSITION,
        GRID_ROWS_COLS,
        RANDOM_POINTS,
        RANDOM_POINTS.replace(shape=Shape.ELLIPSE),
        RANDOM_POINTS.replace(fov_width=None),
        RANDOM_POINTS.replace(fov_width=None, fov_height=None),
    ],
)
def test_points_plan_variants(plan: useq.RelativeMultiPointPlan, qtbot: QtBot) -> None:
    """Test PointsPlanWidget with different plan types."""
    wdg = pp.PointsPlanWidget(plan)
    wdg.show()
    qtbot.addWidget(wdg)
    # make sure the view can also render without a well size
    wdg._well_view.setWellSize(None, None)
    wdg._well_view.setPointsPlan(plan)
    assert wdg.value() == plan


@pytest.mark.skipif(qtpy.QT5, reason="QMouseEvent API changed")
def test_clicking_point_changes_first_position(qtbot: QtBot) -> None:
    plan = RandomPoints(
        num_points=20,
        random_seed=0,
        fov_width=500,
        fov_height=500,
        max_width=5000,
        max_height=5000,
    )
    wdg = pp.PointsPlanWidget(plan)
    wdg.show()
    qtbot.addWidget(wdg)

    assert isinstance(wdg.value().start_at, int)

    # clicking on a point should change the start_at position
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        wdg._well_view.mapFromScene(0, 0).toPointF(),
        wdg._well_view.mapFromScene(0, 0).toPointF(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    wdg._well_view.mousePressEvent(event)

    new_val = wdg.value()
    assert isinstance(new_val.start_at, useq.RelativePosition)
    rounded = round(new_val.start_at)
    # feel free to relax this if it ever fails tests
    assert rounded.x == 108
    assert rounded.y == -44


def test_max_points_detected(qtbot: QtBot) -> None:
    plan = RandomPoints(
        num_points=20,
        random_seed=0,
        fov_width=500,
        fov_height=500,
        max_width=1000,
        max_height=1000,
        allow_overlap=False,
    )
    wdg = pp.PointsPlanWidget(plan)
    wdg.show()
    qtbot.addWidget(wdg)

    with qtbot.waitSignal(wdg._well_view.maxPointsDetected):
        wdg._selector.random_points_wdg.num_points.setValue(100)

    assert wdg.value().num_points < 60


def test_set_well_area(qtbot: QtBot) -> None:
    wdg = pp.PointsPlanWidget()

    with qtbot.waitSignal(wdg._well_view.wellSizeSet):
        wdg.setWellSize(3, 3)
    assert wdg._selector.random_points_wdg.max_width.maximum() == 3000
    assert wdg._selector.random_points_wdg.max_height.maximum() == 3000

    plan = RandomPoints(
        num_points=20, fov_width=500, fov_height=500, max_width=4000, max_height=4000
    )
    wdg.setValue(plan)
    # max_width and max_height should be capped at 3000
    assert wdg.value().max_width == 3000
    assert wdg.value().max_height == 3000

    with qtbot.waitSignal(wdg._well_view.wellSizeSet):
        wdg.setWellSize(None, None)
    assert wdg._well_view._outline_item is None
    assert wdg._well_view._bounding_area is None


def test_restricted_area(qtbot: QtBot) -> None:
    wdg = pp.PointsPlanWidget()
    wdg.show()

    wdg.setWellSize(3, 3)
    plan = RandomPoints(
        num_points=20, fov_width=200, fov_height=300, max_width=1500, max_height=1000
    )
    wdg.setValue(plan)

    well_rect = wdg._well_view._outline_item.sceneBoundingRect()
    bounding_rect = wdg._well_view._bounding_area.sceneBoundingRect()

    # both rects should have the same center
    assert well_rect.center() == bounding_rect.center()
    offset = 20  # ofset automatically added when using addEllipse
    # bounding rect should be 1/2 the size of the well rect in width
    assert well_rect.width() - offset == (bounding_rect.width() - offset) * 2
    # bounding rect should be 1/3 the size of the well rect in height
    assert well_rect.height() - offset == (bounding_rect.height() - offset) * 3
