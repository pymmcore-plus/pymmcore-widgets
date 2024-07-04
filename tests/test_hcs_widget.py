from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple
from unittest.mock import patch

import pytest
from qtpy.QtWidgets import (
    QFileDialog,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
)
from useq import GridRowsColumns, RandomPoints, WellPlate, WellPlatePlan
from useq._grid import Shape

from pymmcore_widgets import HCSWizard
from pymmcore_widgets.hcs._calibration_widget._calibration_sub_widgets import (
    ROLE,
    FourPoints,
    OnePoint,
    ThreePoints,
    TwoPoints,
    _CalibrationModeWidget,
    _CalibrationTable,
    _TestCalibrationWidget,
)
from pymmcore_widgets.hcs._calibration_widget._calibration_widget import (
    CalibrationData,
    PlateCalibrationWidget,
)
from pymmcore_widgets.hcs._fov_widget._fov_sub_widgets import (
    Center,
    _CenterFOVWidget,
    _GridFovWidget,
    _RandomFOVWidget,
    _WellView,
    _WellViewData,
)
from pymmcore_widgets.hcs._fov_widget._fov_widget import FOVSelectorWidget
from pymmcore_widgets.hcs._graphics_items import (
    Well,
    _FOVGraphicsItem,
    _WellAreaGraphicsItem,
)
from pymmcore_widgets.hcs._plate_widget import (
    PlateInfo,
    PlateSelectorWidget,
)
from pymmcore_widgets.hcs._util import load_database

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


@pytest.fixture()
def database_path():
    return Path(__file__).parent / "plate_database_for_tests.json"


@pytest.fixture()
def database(database_path):
    return load_database(database_path)


CUSTOM_PLATE = WellPlate(
    rows=2,
    columns=4,
    well_spacing=(15, 15),
    well_size=(10, 10),
    circular_wells=True,
    name="custom plate",
)


def test_plate_selector_widget_set_get_value(qtbot: QtBot, database_path: Path):
    wdg = PlateSelectorWidget(plate_database_path=database_path)
    qtbot.addWidget(wdg)

    info = PlateInfo(plate=CUSTOM_PLATE, wells=[])

    with pytest.raises(ValueError, match="'custom plate' not in the database."):
        wdg.setValue(info)

    plate = wdg._plate_db["96-well"]
    wells = [
        Well(name="A1", row=0, column=0),
        Well(name="A2", row=0, column=1),
        Well(name="B3", row=1, column=2),
        Well(name="B4", row=1, column=3),
        Well(name="C5", row=2, column=4),
    ]
    info = PlateInfo(plate=plate, wells=wells)

    wdg.setValue(info)
    # sort the list of wells by name
    assert sorted(wdg.scene.value(), key=lambda x: x.name) == wells

    wdg._clear_button.click()
    assert wdg.scene.value() == []


def test_plate_selector_widget_combo(qtbot: QtBot, database_path: Path):
    wdg = PlateSelectorWidget(plate_database_path=database_path)
    qtbot.addWidget(wdg)

    wdg.plate_combo.setCurrentText("96-well")
    assert wdg.value().plate.name == "96-well"


def test_plate_selector_widget_get_database(qtbot: QtBot, database_path: Path):
    wdg = PlateSelectorWidget(plate_database_path=database_path)
    qtbot.addWidget(wdg)

    assert wdg.database() == wdg._plate_db


def test_calibration_mode_widget(qtbot: QtBot):
    wdg = _CalibrationModeWidget()
    qtbot.addWidget(wdg)

    modes = [TwoPoints(), ThreePoints(), FourPoints()]
    wdg.setValue(modes)

    assert wdg._mode_combo.count() == 3

    for i in range(wdg._mode_combo.count()):
        assert wdg._mode_combo.itemData(i, ROLE) == modes[i]


def test_calibration_table_widget(
    global_mmcore: CMMCorePlus, qtbot: QtBot, database: dict[str, WellPlate]
):
    mmc = global_mmcore

    wdg = _CalibrationTable(mmcore=mmc)
    qtbot.addWidget(wdg)

    assert wdg.table().rowCount() == 0
    assert wdg._well_label.text() == " Well "

    wdg.setLabelText(" Well A1 ")
    assert wdg.getLabelText() == " Well A1 "

    mmc.setXYPosition(mmc.getXYStageDevice(), -10, 10)
    mmc.waitForSystem()
    wdg.act_add_row.trigger()
    assert wdg.table().rowCount() == 1
    assert wdg.table().cellWidget(0, 0).value() == -10
    assert wdg.table().cellWidget(0, 1).value() == 10

    mmc.setXYPosition(mmc.getXYStageDevice(), 10, -10)
    mmc.waitForSystem()
    wdg.act_add_row.trigger()
    assert wdg.table().rowCount() == 2
    assert wdg.table().cellWidget(1, 0).value() == 10
    assert wdg.table().cellWidget(1, 1).value() == -10

    assert wdg.value() == [(-10, 10), (10, -10)]


def test_calibration_move_to_edge_widget(
    global_mmcore: CMMCorePlus, qtbot: QtBot, database: dict[str, WellPlate]
):
    mmc = global_mmcore

    wdg = _TestCalibrationWidget(mmcore=mmc)
    qtbot.addWidget(wdg)

    assert wdg._letter_combo.count() == 0
    assert wdg._number_combo.count() == 0

    well = Well(name="C3", row=2, column=2)
    wdg.setValue(database["96-well"], well)
    assert wdg._letter_combo.count() == 8
    assert wdg._number_combo.count() == 12
    assert wdg.value() == (database["96-well"], well)


def test_calibration_widget(
    global_mmcore: CMMCorePlus, qtbot: QtBot, database: dict[str, WellPlate]
):
    wdg = PlateCalibrationWidget(mmcore=global_mmcore)
    qtbot.addWidget(wdg)

    assert wdg.value() is None
    assert wdg._calibration_label.value() == "Plate Not Calibrated!"

    plate = database["coverslip-22mm"]
    cal = CalibrationData(plate=plate)

    wdg.setValue(cal)

    assert wdg._calibration_mode._mode_combo.count() == 2
    assert wdg._calibration_mode._mode_combo.itemData(0, ROLE) == TwoPoints()
    assert wdg._calibration_mode._mode_combo.itemData(1, ROLE) == FourPoints()
    assert isinstance(wdg._calibration_mode.value(), TwoPoints)

    assert not wdg._table_a1.isHidden()
    assert wdg._table_an.isHidden()
    assert not wdg.isCalibrated()
    assert wdg._calibration_label.value() == "Plate Not Calibrated!"
    assert wdg.value() == cal

    wdg._table_a1.setValue([(-210, 170), (100, -100)])
    pos = wdg._table_a1.value()
    assert pos
    assert len(pos) == 2

    wdg._on_calibrate_button_clicked()

    assert wdg.isCalibrated()
    assert wdg._calibration_label.value() == "Plate Calibrated!"
    assert wdg.value() == CalibrationData(
        calibrated=True,
        plate=plate,
        a1_center_xy=(-55.0, 35.0),
        rotation=0.0,
        calibration_positions_a1=[(-210, 170), (100, -100)],
        calibration_positions_an=[],
    )

    plate = database["96-well"]
    cal = CalibrationData(plate=plate)
    wdg.setValue(cal)

    assert not wdg.isCalibrated()

    assert wdg._calibration_mode._mode_combo.count() == 2
    assert wdg._calibration_mode._mode_combo.itemData(0, ROLE) == OnePoint()
    assert wdg._calibration_mode._mode_combo.itemData(1, ROLE) == ThreePoints()

    assert not wdg._table_a1.isHidden()
    assert not wdg._table_an.isHidden()

    assert wdg._table_a1.getLabelText() == " Well A1 "
    assert wdg._table_an.getLabelText() == " Well A12 "

    wdg.setValue(None)
    assert wdg._table_a1.isHidden()
    assert wdg._table_an.isHidden()
    assert wdg.value() is None


def test_center_widget(qtbot: QtBot):
    wdg = _CenterFOVWidget()
    qtbot.addWidget(wdg)

    value = wdg.value()

    assert value.x == value.y == 0.0
    assert value.fov_width == value.fov_height is None

    wdg.fov_size = (5, 7)
    value = wdg.value()
    assert value.fov_width == 5
    assert value.fov_height == 7

    wdg.setValue(Center(x=10, y=20, fov_width=2, fov_height=3))

    value = wdg.value()
    assert value.x == 10
    assert value.y == 20
    assert value.fov_width == 2
    assert value.fov_height == 3


def test_random_widget(qtbot: QtBot, database: dict[str, WellPlate]):
    wdg = _RandomFOVWidget()
    qtbot.addWidget(wdg)

    assert not wdg.is_circular

    value = wdg.value()
    assert value.fov_width == value.fov_height is None
    assert value.num_points == 1
    assert value.max_width == value.max_height == 0.0
    assert value.shape.value == "rectangle"
    assert isinstance(value.random_seed, int)

    wdg.fov_size = (2, 2)
    value = wdg.value()
    assert value.fov_width == value.fov_height == 2

    wdg.setValue(
        RandomPoints(
            num_points=10,
            max_width=20,
            max_height=30,
            shape="ellipse",
            random_seed=0,
            fov_width=5,
            fov_height=5,
        )
    )
    value = wdg.value()
    assert value.num_points == 10
    assert value.max_width == 20
    assert value.max_height == 30
    assert value.random_seed == 0
    assert wdg.is_circular
    assert value.fov_width == value.fov_height == 5

    wdg.reset()
    value = wdg.value()
    assert not wdg.is_circular
    assert value.num_points == 1
    assert value.max_width == value.max_height == 0.0
    assert value.fov_height is None
    assert value.fov_width is None


def test_grid_widget(qtbot: QtBot):
    wdg = _GridFovWidget()
    qtbot.addWidget(wdg)

    value = wdg.value()
    assert value.fov_width == value.fov_height is None
    assert value.overlap == (0.0, 0.0)
    assert value.mode.value == "row_wise_snake"
    assert value.rows == value.columns == 1
    assert value.relative_to.value == "center"

    wdg.fov_size = (0.512, 0.512)
    value = wdg.value()
    assert value.fov_width == value.fov_height == 0.512

    wdg.setValue(
        GridRowsColumns(
            overlap=10.0,
            mode="row_wise",
            rows=2,
            columns=3,
            fov_width=2,
            fov_height=2,
        )
    )
    value = wdg.value()
    assert value.overlap == (10.0, 10.0)
    assert value.mode.value == "row_wise"
    assert value.rows == 2
    assert value.columns == 3
    assert value.relative_to.value == "center"
    assert value.fov_width == value.fov_height == 2

    wdg.reset()
    value = wdg.value()
    assert value.fov_width == value.fov_height is None
    assert value.overlap == (0.0, 0.0)
    assert value.rows == value.columns == 1


class SceneItems(NamedTuple):
    fovs: int  # _FOVGraphicsItem
    lines: int  # QGraphicsLineItem
    well_area: int  # _WellAreaGraphicsItem
    well_circle: int  # QGraphicsEllipseItem
    well_rect: int  # QGraphicsRectItem


def get_items_number(wdg: _WellView) -> SceneItems:
    """Return the number of items in the scene as a SceneItems namedtuple."""
    items = wdg.scene().items()
    fovs = len([t for t in items if isinstance(t, _FOVGraphicsItem)])
    lines = len([t for t in items if isinstance(t, QGraphicsLineItem)])
    well_area = len([t for t in items if isinstance(t, _WellAreaGraphicsItem)])
    well_circle = len([t for t in items if isinstance(t, QGraphicsEllipseItem)])
    well_rect = len([t for t in items if isinstance(t, QGraphicsRectItem)])
    return SceneItems(fovs, lines, well_area, well_circle, well_rect)


modes = [
    (
        Center(x=0, y=0, fov_width=512, fov_height=512),
        SceneItems(fovs=1, lines=0, well_area=0, well_circle=0, well_rect=1),
    ),
    (
        RandomPoints(
            num_points=3,
            max_width=5,
            max_height=4,
            shape="ellipse",
            fov_width=510,
            fov_height=510,
        ),
        SceneItems(fovs=3, lines=2, well_area=1, well_circle=1, well_rect=0),
    ),
    (
        GridRowsColumns(rows=2, columns=3, fov_width=500, fov_height=500),
        SceneItems(fovs=6, lines=5, well_area=0, well_circle=0, well_rect=1),
    ),
]


@pytest.mark.parametrize(["mode", "items"], modes)
def test_well_view_widget_value(
    qtbot: QtBot, mode: Center | GridRowsColumns | RandomPoints, items: SceneItems
):
    wdg = _WellView()
    qtbot.addWidget(wdg)
    assert wdg.value() == _WellViewData()

    circular = mode.shape == Shape.ELLIPSE if isinstance(mode, RandomPoints) else False
    view_data = _WellViewData(
        well_size=(6400, 6400),
        circular=circular,
        padding=20,
        mode=mode,
    )
    wdg.setValue(view_data)

    assert wdg.value() == view_data
    assert wdg.isCircular() if isinstance(mode, RandomPoints) else not wdg.isCircular()

    # make sure that the graphics item in the scene are the expected ones
    assert get_items_number(wdg) == items


def test_well_view_widget_update(qtbot: QtBot):
    view_data = _WellViewData(
        well_size=(6400, 6400),
        mode=Center(x=0, y=0, fov_width=512, fov_height=512),
    )
    wdg = _WellView(data=view_data)
    qtbot.addWidget(wdg)

    # set mode
    grid = GridRowsColumns(rows=3, columns=3, fov_width=512, fov_height=512)
    wdg.setMode(grid)

    # set fov size
    fovs = get_items_number(wdg).fovs
    assert fovs == 9

    # set circular
    assert not wdg.isCircular()
    _, _, _, well_circle, well_rect = get_items_number(wdg)
    assert well_circle == 0
    assert well_rect == 1

    wdg.setCircular(True)
    wdg.refresh()
    assert wdg.isCircular()
    _, _, _, well_circle, well_rect = get_items_number(wdg)
    assert well_circle == 1
    assert well_rect == 0

    # set padding
    assert not wdg.padding()
    well = next(t for t in wdg.scene().items() if isinstance(t, QGraphicsEllipseItem))
    assert well.rect().width() == well.rect().height() == 300

    wdg.setPadding(10)
    assert wdg.padding() == 10
    wdg.refresh()
    well = next(t for t in wdg.scene().items() if isinstance(t, QGraphicsEllipseItem))
    assert well.rect().width() == well.rect().height() == 290

    # set mode to None
    wdg.setMode(None)
    assert not get_items_number(wdg).fovs


def test_fov_selector_widget_none(qtbot: QtBot):
    wdg = FOVSelectorWidget()
    qtbot.addWidget(wdg)

    assert wdg.value() == (None, Center(x=0.0, y=0.0))
    assert get_items_number(wdg.view) == SceneItems(
        fovs=0, lines=0, well_area=0, well_circle=0, well_rect=0
    )


def test_fov_selector_widget(qtbot: QtBot, database: dict[str, WellPlate]):
    plate = database["96-well"]
    wdg = FOVSelectorWidget(
        plate=plate,
        mode=Center(x=0, y=0, fov_width=500, fov_height=500),
    )
    qtbot.addWidget(wdg)

    # center
    assert wdg.value() == (
        plate,
        Center(x=0, y=0, fov_width=500, fov_height=500),
    )

    # grid
    grid = GridRowsColumns(overlap=10, rows=2, columns=3, fov_width=512, fov_height=512)
    coverslip = database["coverslip-22mm"]
    wdg.setValue(coverslip, grid)

    current_plate, mode = wdg.value()
    assert current_plate == coverslip
    assert mode.fov_width == mode.fov_height == 512
    assert mode.rows == 2
    assert mode.columns == 3
    assert mode.overlap == (10.0, 10.0)

    # random
    rnd = RandomPoints(
        num_points=2,
        max_width=10,
        max_height=10,
        shape="rectangle",
        fov_width=600,
        fov_height=500,
        random_seed=0,
    )

    wdg.setValue(coverslip, rnd)

    current_plate, mode = wdg.value()
    assert mode.max_width == mode.max_height == 10
    assert mode.num_points == 2
    assert mode.fov_width == 600
    assert mode.fov_height == 500
    assert mode.shape.value == "rectangle"
    assert mode.random_seed == 0

    # warning well RandomPoints shape > plate area_X
    with pytest.raises(UserWarning, match="RandomPoints `max_width`"):
        rnd = RandomPoints(
            num_points=2, max_width=30000, max_height=30000, shape="ellipse"
        )
        wdg.setValue(plate, rnd)

    # none
    wdg.setValue(coverslip, None)
    current_plate, _ = wdg.value()
    assert current_plate == coverslip
    assert get_items_number(wdg.view) == SceneItems(
        fovs=0, lines=0, well_area=0, well_circle=0, well_rect=1
    )

    wdg.setValue(None, Center(x=0, y=0, fov_width=500, fov_height=500))
    current_plate, mode = wdg.value()
    assert current_plate is None
    assert mode == Center(x=0, y=0, fov_width=500, fov_height=500)
    assert mode.fov_width == mode.fov_height == 500
    assert get_items_number(wdg.view) == SceneItems(
        fovs=0, lines=0, well_area=0, well_circle=0, well_rect=0
    )


@pytest.fixture
def data(database) -> WellPlatePlan:
    plate = database["96-well"]
    return WellPlatePlan(
        plate=plate,
        a1_center_xy=(100.0, 200.0),
        rotation=10.0,
        selected_wells=([0, 1, 2], [0, 1, 2]),
        well_points_plan=RandomPoints(
            num_points=3,
            max_width=6400,
            max_height=6400,
            shape="ellipse",
            fov_width=512,
            fov_height=512,
            allow_overlap=False,
            random_seed=10,
        ),
    )


def test_hcs_wizard_set_get_value(
    data: WellPlatePlan,
    global_mmcore: CMMCorePlus,
    qtbot: QtBot,
):
    wdg = HCSWizard()
    qtbot.addWidget(wdg)

    wdg.setValue(data)

    assert wdg.value() == data
    assert wdg.calibration_page.isCalibrated()


def test_save_load_hcs(
    data: WellPlatePlan, qtbot: QtBot, tmp_path: Path, database: dict[str, WellPlate]
):
    wdg = HCSWizard()
    qtbot.addWidget(wdg)

    wdg.setValue(data)

    file = tmp_path / "test.json"
    assert not file.exists()

    def _path(*args, **kwargs):
        return file, None

    # create empty database
    with patch.object(QFileDialog, "getSaveFileName", _path):
        wdg._save()

        assert file.exists()

        # change plate
        plate = database["6-well"]
        wdg.plate_page.setValue(PlateInfo(plate, []))
        assert wdg.value() != data

        # load the saved data
        with patch.object(QFileDialog, "getOpenFileName", _path):
            wdg._load()
            assert wdg.value() == data
