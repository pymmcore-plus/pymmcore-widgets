from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import pytest
import qtpy
import useq
from qtpy.QtCore import Qt
from qtpy.QtGui import QMouseEvent
from qtpy.QtWidgets import QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsRectItem
from useq import GridRowsColumns, OrderMode, RandomPoints, RelativePosition, Shape

from pymmcore_widgets.useq_widgets import points_plans as pp

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

    from pymmcore_widgets.useq_widgets.points_plans._well_graphics_view import WellView

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
    assert wdg.num_points.value() == 10
    assert wdg.max_width.value() == 6000
    assert wdg.max_height.value() == 6000
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
    assert wdg.rows.value() == 3
    assert wdg.columns.value() == 3
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
        wdg.random_points_wdg.num_points.setValue(100)

    assert wdg.value().num_points < 60


def test_points_plan_set_well_info(qtbot: QtBot) -> None:
    wdg = pp.PointsPlanWidget()
    wdg.show()

    assert wdg._well_view._well_outline_item is None
    assert wdg._well_view._bounding_area_item is None
    assert wdg._well_view._well_is_circular

    wdg.setWellSize(3, 3)

    assert wdg._well_view._well_outline_item
    assert wdg._well_view._well_outline_item.isVisible()
    assert isinstance(wdg._well_view._well_outline_item, QGraphicsEllipseItem)

    wdg.setWellShape("square")
    assert isinstance(wdg._well_view._well_outline_item, QGraphicsRectItem)

    wdg.setWellShape("circle")
    assert isinstance(wdg._well_view._well_outline_item, QGraphicsEllipseItem)

    plan = RandomPoints(
        num_points=3, fov_width=500, fov_height=0, max_width=1000, max_height=1500
    )
    wdg.setValue(plan)

    assert wdg._well_view._bounding_area_item
    assert wdg._well_view._bounding_area_item.isVisible()
    assert isinstance(wdg._well_view._bounding_area_item, QGraphicsEllipseItem)

    well = wdg._well_view._well_outline_item.sceneBoundingRect()
    bound = wdg._well_view._bounding_area_item.sceneBoundingRect()
    assert well.center() == bound.center()
    offset = 20  # offset automatically added when drawing
    # bounding rect should be 1/3 the size of the well rect in width
    assert well.width() - offset == (bound.width() - offset) * 3
    # bounding rect should be 1/2 the size of the well rect in height
    assert well.height() - offset == (bound.height() - offset) * 2

    wdg.setWellSize(None, None)
    assert wdg._well_view._well_outline_item is None


class SceneItems(NamedTuple):
    rect: int  # QGraphicsRectItem (fovs/well area/bounding area)
    lines: int  # QGraphicsLineItem (fovs lines)
    circles: int  # QGraphicsEllipseItem (well area/bounding area)


def get_items_number(view: WellView) -> SceneItems:
    """Return the number of items in the scene as a SceneItems namedtuple."""
    items = view.scene().items()
    lines = len([ln for ln in items if isinstance(ln, QGraphicsLineItem)])
    circles = len([c for c in items if isinstance(c, QGraphicsEllipseItem)])
    rect = len([r for r in items if isinstance(r, QGraphicsRectItem)])
    return SceneItems(rect, lines, circles)


# fmt: off
rp = RandomPoints(num_points=3, max_width=1000, max_height=1000,fov_width=410, fov_height=300, random_seed=0)  # noqa E501
plans = [
    # plan, well_shape, expected number of QGraphicsItems
    (useq.RelativePosition(), "square", SceneItems(rect=0, lines=0, circles=2)),
    (useq.RelativePosition(fov_width=100, fov_height=50), "circle", SceneItems(rect=1, lines=0, circles=1)),  # noqa E501
    (rp, "ellipse", SceneItems(rect=3, lines=2, circles=2)),
    (rp.replace(shape="rectangle"),"rectangle", SceneItems(rect=4, lines=2, circles=1)),
    (GridRowsColumns(rows=2, columns=3, fov_width=400, fov_height=500), "circle", SceneItems(rect=6, lines=5, circles=1))  # noqa E501
]
# fmt: on


# make sure that the correct QGraphicsItems are drawn in the scene
@pytest.mark.parametrize(["plan", "shape", "expedted_items"], plans)
def test_points_plan_plans(
    qtbot: QtBot,
    plan: useq.RelativeMultiPointPlan,
    shape: str,
    expedted_items: SceneItems,
):
    wdg = pp.PointsPlanWidget(plan=plan)
    wdg.setWellSize(3, 3)  # fix well size
    wdg.setWellShape("circle")  # fix well shape
    wdg.show()
    assert get_items_number(wdg._well_view) == expedted_items


@pytest.mark.parametrize(["plan", "shape", "expedted_items"], plans)
def test_points_plan_set_get_value(
    qtbot: QtBot,
    plan: useq.RelativeMultiPointPlan,
    shape: str,
    expedted_items: SceneItems,
):
    wdg = pp.PointsPlanWidget()
    wdg.setWellSize(3, 3)  # fix well size
    wdg.setWellShape("circle")  # fix well shape
    wdg.show()

    wdg.setValue(plan)

    assert get_items_number(wdg._well_view) == expedted_items
    assert wdg.value() == plan
