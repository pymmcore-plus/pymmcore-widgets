from __future__ import annotations

import json
import tempfile
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
from useq import (  # type: ignore
    AnyGridPlan,
    GridFromEdges,
    GridRowsColumns,
    RandomPoints,
)
from useq._grid import Shape

from pymmcore_widgets import HCSWizard
from pymmcore_widgets.hcs._calibration_widget import (
    ROLE,
    CalibrationData,
    FourPoints,
    PlateCalibrationWidget,
    ThreePoints,
    TwoPoints,
    _CalibrationModeWidget,
    _CalibrationTable,
    _TestCalibrationWidget,
)
from pymmcore_widgets.hcs._fov_widget import (
    Center,
    FOVSelectorWidget,
    WellView,
    WellViewData,
    _CenterFOVWidget,
    _GridFovWidget,
    _RandomFOVWidget,
)
from pymmcore_widgets.hcs._graphics_items import (
    Well,
    _FOVGraphicsItem,
    _WellAreaGraphicsItem,
    _WellGraphicsItem,
)
from pymmcore_widgets.hcs._main_wizard_widget import HCSData
from pymmcore_widgets.hcs._plate_model import Plate, load_database
from pymmcore_widgets.hcs._plate_widget import (
    PlateDatabaseWidget,
    PlateInfo,
    PlateSelectorWidget,
)

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


@pytest.fixture()
def database_path():
    return Path(__file__).parent / "plate_database_for_tests.json"


@pytest.fixture()
def database(database_path):
    return load_database(database_path)


CUSTOM_PLATE = Plate(
    id="custom plate",
    circular=True,
    rows=2,
    columns=4,
    well_spacing_x=15,
    well_spacing_y=15,
    well_size_x=10,
    well_size_y=10,
)


def test_plate_selector_widget_load_database(qtbot: QtBot, database_path: Path):
    wdg = PlateSelectorWidget()
    qtbot.addWidget(wdg)

    assert "coverslip 10mm" not in wdg._plate_db
    assert "coverslip 10mm" not in wdg._plate_db_wdg._plate_db

    wdg.load_database(database_path)

    assert "coverslip 10mm" in wdg._plate_db
    assert "coverslip 10mm" in wdg._plate_db_wdg._plate_db


def test_plate_selector_widget_load_database_db_wdg(qtbot: QtBot, database_path: Path):
    wdg = PlateSelectorWidget()
    qtbot.addWidget(wdg)

    assert "coverslip 10mm" not in wdg._plate_db
    assert "coverslip 10mm" not in wdg._plate_db_wdg._plate_db

    wdg._plate_db_wdg.load_database(database_path)

    assert "coverslip 10mm" in wdg._plate_db
    assert "coverslip 10mm" in wdg._plate_db_wdg._plate_db


def test_plate_selector_widget_load_database_dialog(qtbot: QtBot, database_path: Path):
    wdg = PlateSelectorWidget()
    qtbot.addWidget(wdg)

    assert "coverslip 10mm" not in wdg._plate_db
    assert "coverslip 10mm" not in wdg._plate_db_wdg._plate_db

    def _path(*args, **kwargs):
        return database_path, None

    with patch.object(QFileDialog, "getOpenFileName", _path):
        wdg.load_database()
    assert "coverslip 10mm" in wdg._plate_db
    assert "coverslip 10mm" in wdg._plate_db_wdg._plate_db


def test_plate_selector_widget_set_get_value(qtbot: QtBot, database_path: Path):
    wdg = PlateSelectorWidget(plate_database_path=database_path)
    qtbot.addWidget(wdg)

    info = PlateInfo(plate=CUSTOM_PLATE, wells=None)

    with pytest.raises(ValueError, match="'custom plate' not in the database."):
        wdg.setValue(info)

    plate = wdg._plate_db["standard 96 wp"]
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
    assert wdg.scene.value() is None


def test_plate_selector_widget_combo(qtbot: QtBot, database_path: Path):
    wdg = PlateSelectorWidget(plate_database_path=database_path)
    qtbot.addWidget(wdg)

    wdg.plate_combo.setCurrentText("standard 96 wp")
    assert wdg.value().plate.id == "standard 96 wp"


def test_plate_selector_widget_get_database(qtbot: QtBot, database_path: Path):
    wdg = PlateSelectorWidget(plate_database_path=database_path)
    qtbot.addWidget(wdg)

    assert wdg.database() == wdg._plate_db == wdg._plate_db_wdg._plate_db


def test_plate_database_widget_load_database(qtbot: QtBot, database_path: Path):
    wdg = PlateDatabaseWidget()
    qtbot.addWidget(wdg)

    assert "coverslip 10mm" not in wdg._plate_db

    wdg.load_database(database_path)

    assert "coverslip 10mm" in wdg._plate_db


def test_plate_database_widget_set_get_value(qtbot: QtBot, database_path: Path):
    wdg = PlateDatabaseWidget(plate_database_path=database_path)
    qtbot.addWidget(wdg)

    current_plate_id = wdg.plate_table.item(0, 0).text()
    assert wdg.value().id == current_plate_id

    wdg.setValue(CUSTOM_PLATE)
    assert wdg.value() == CUSTOM_PLATE

    scene_items = list(wdg.scene.items())
    assert len(scene_items) == 8
    assert all(isinstance(item, _WellGraphicsItem) for item in scene_items)


def test_plate_database_widget_update_database(qtbot: QtBot, database_path: Path):
    wdg = PlateDatabaseWidget(plate_database_path=database_path)
    qtbot.addWidget(wdg)

    assert "custom plate" not in wdg._plate_db
    wdg.setValue(CUSTOM_PLATE)

    wdg._add_to_database()
    assert "custom plate" in wdg._plate_db
    plates = [
        wdg.plate_table.item(i, 0).text() for i in range(wdg.plate_table.rowCount())
    ]
    assert "custom plate" in plates

    wdg.plate_table.selectRow(0)
    last_row = wdg.plate_table.rowCount() - 1
    wdg.plate_table.selectRow(last_row)

    assert wdg.plate_table.item(last_row, 0).text() == "custom plate"

    wdg._remove_from_database()
    assert "custom plate" not in wdg._plate_db
    plates = [
        wdg.plate_table.item(i, 0).text() for i in range(wdg.plate_table.rowCount())
    ]
    assert "custom plate" not in plates


def test_plate_database_widget_database(qtbot: QtBot, database_path: Path):
    wdg = PlateDatabaseWidget(plate_database_path=database_path)
    qtbot.addWidget(wdg)

    assert wdg.database()
    assert "custom plate" not in wdg.database()

    with tempfile.TemporaryDirectory() as tmp:

        def _path(*args, **kwargs):
            return Path(tmp) / "test_db.json", None

        # create empty database
        with patch.object(QFileDialog, "getSaveFileName", _path):
            wdg._create_new_database()
        assert wdg._plate_db_path == _path()[0]
        assert not wdg.database()

        # add plate to database
        wdg.add_to_database([CUSTOM_PLATE])
        assert wdg.database()
        assert "custom plate" in wdg.database()

        # remove plate from database
        wdg.remove_from_database(["custom plate"])
        assert not wdg.database()
        assert "custom plate" not in wdg.database()


def test_plate_database_widget_empty_name(qtbot: QtBot, database_path: Path):
    wdg = PlateDatabaseWidget(plate_database_path=database_path)
    qtbot.addWidget(wdg)

    wdg._id.setText("")

    with pytest.raises(ValueError, match="'Plate Name' field cannot be empty!"):
        wdg._add_to_database()


def test_plate_database_widget_get_database(qtbot: QtBot, database_path: Path):
    wdg = PlateDatabaseWidget(plate_database_path=database_path)
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
    global_mmcore: CMMCorePlus, qtbot: QtBot, database: dict[str, Plate]
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
    global_mmcore: CMMCorePlus, qtbot: QtBot, database: dict[str, Plate]
):
    mmc = global_mmcore

    wdg = _TestCalibrationWidget(mmcore=mmc)
    qtbot.addWidget(wdg)

    assert wdg._letter_combo.count() == 0
    assert wdg._number_combo.count() == 0

    well = Well(name="C3", row=2, column=2)
    wdg.setValue(database["standard 96 wp"], well)
    assert wdg._letter_combo.count() == 8
    assert wdg._number_combo.count() == 12
    assert wdg.value() == (database["standard 96 wp"], well)


def test_calibration_widget(
    global_mmcore: CMMCorePlus, qtbot: QtBot, database: dict[str, Plate]
):
    wdg = PlateCalibrationWidget(mmcore=global_mmcore)
    qtbot.addWidget(wdg)

    assert wdg.value() is None
    assert wdg._calibration_label.value() == "Plate Not Calibrated!"

    wdg.setValue(CalibrationData(plate=database["coverslip 22mm"]))

    assert wdg._calibration_mode._mode_combo.count() == 2
    assert wdg._calibration_mode._mode_combo.itemData(0, ROLE) == TwoPoints()
    assert wdg._calibration_mode._mode_combo.itemData(1, ROLE) == FourPoints()
    assert isinstance(wdg._calibration_mode.value(), TwoPoints)

    assert not wdg._table_a1.isHidden()
    assert wdg._table_an.isHidden()
    assert wdg._calibration_label.value() == "Plate Not Calibrated!"
    assert wdg.value() == CalibrationData(plate=database["coverslip 22mm"])

    wdg._table_a1.setValue([(-210, 170), (100, -100)])
    pos = wdg._table_a1.value()
    assert pos
    assert len(pos) == 2

    wdg._on_calibrate_button_clicked()

    assert wdg._calibration_label.value() == "Plate Calibrated!"

    assert wdg.value() == CalibrationData(
        plate=database["coverslip 22mm"],
        well_A1_center=(-55.0, 35.0),
        rotation_matrix=None,
        calibration_positions_a1=[(-210, 170), (100, -100)],
    )

    wdg.setValue(CalibrationData(plate=database["standard 96 wp"]))

    assert wdg._calibration_mode._mode_combo.count() == 1
    assert wdg._calibration_mode._mode_combo.itemData(0, ROLE) == ThreePoints()

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


def test_random_widget(qtbot: QtBot, database: dict[str, Plate]):
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


def get_items_number(wdg: WellView) -> SceneItems:
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
    (
        GridFromEdges(
            top=-20, left=-20, bottom=20, right=20, fov_width=600, fov_height=600
        ),
        SceneItems(fovs=9, lines=8, well_area=0, well_circle=0, well_rect=1),
    ),
]


@pytest.mark.parametrize(["mode", "items"], modes)
def test_well_view_widget_value(
    qtbot: QtBot, mode: Center | AnyGridPlan, items: SceneItems
):
    wdg = WellView()
    qtbot.addWidget(wdg)
    assert wdg.value() == WellViewData()

    circular = mode.shape == Shape.ELLIPSE if isinstance(mode, RandomPoints) else False
    view_data = WellViewData(
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
    view_data = WellViewData(
        well_size=(6400, 6400),
        mode=Center(x=0, y=0, fov_width=512, fov_height=512),
    )
    wdg = WellView(data=view_data)
    qtbot.addWidget(wdg)

    # set mode
    grid = GridFromEdges(
        top=-20, left=-20, bottom=20, right=20, fov_width=512, fov_height=512
    )
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


def test_fov_selector_widget(qtbot: QtBot, database: dict[str, Plate]):
    wdg = FOVSelectorWidget(
        plate=database["standard 96 wp"],
        mode=Center(x=0, y=0, fov_width=500, fov_height=500),
    )
    qtbot.addWidget(wdg)

    # center
    assert wdg.value() == (
        database["standard 96 wp"],
        Center(x=0, y=0, fov_width=500, fov_height=500),
    )

    # grid
    grid = GridRowsColumns(overlap=10, rows=2, columns=3, fov_width=512, fov_height=512)
    wdg.setValue(database["coverslip 22mm"], grid)

    plate, mode = wdg.value()
    assert plate == database["coverslip 22mm"]
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

    wdg.setValue(database["coverslip 22mm"], rnd)

    plate, mode = wdg.value()
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
        wdg.setValue(database["standard 96 wp"], rnd)

    # none
    wdg.setValue(database["coverslip 22mm"], None)
    plate, _ = wdg.value()
    assert plate == database["coverslip 22mm"]
    assert get_items_number(wdg.view) == SceneItems(
        fovs=0, lines=0, well_area=0, well_circle=0, well_rect=1
    )

    wdg.setValue(None, Center(x=0, y=0, fov_width=500, fov_height=500))
    plate, mode = wdg.value()
    assert plate is None
    assert mode == Center(x=0, y=0, fov_width=500, fov_height=500)
    assert mode.fov_width == mode.fov_height == 500
    assert get_items_number(wdg.view) == SceneItems(
        fovs=0, lines=0, well_area=0, well_circle=0, well_rect=0
    )


@pytest.fixture
def data(database) -> HCSData:
    return HCSData(
        plate=database["standard 96 wp"],
        wells=[
            Well(name="A1", row=0, column=0),
            Well(name="B2", row=1, column=1),
            Well(name="C3", row=2, column=2),
        ],
        mode=RandomPoints(
            num_points=3,
            max_width=600,
            max_height=600,
            shape="ellipse",
            fov_width=10,
            fov_height=10,
            allow_overlap=False,
        ),
        calibration=CalibrationData(
            plate=database["standard 96 wp"],
            calibration_positions_a1=[(-10.0, 0.0), (0.0, 10.0), (10.0, 0.0)],
            calibration_positions_an=[(90.0, 0.0), (100.0, 10.0), (110.0, 0.0)],
            rotation_matrix=[[1.0, 0.0], [0.0, 1.0]],
        ),
    )


def test_hcs_wizard(
    data: HCSData, global_mmcore: CMMCorePlus, qtbot: QtBot, database: dict[str, Plate]
):
    wdg = HCSWizard()
    qtbot.addWidget(wdg)
    mmc = global_mmcore

    width = mmc.getImageWidth() * mmc.getPixelSizeUm()
    height = mmc.getImageHeight() * mmc.getPixelSizeUm()
    data = data.replace(mode=Center(x=0, y=0, fov_width=width, fov_height=height))

    wdg.setValue(data)

    wdg.calibration_page._calibration._on_calibrate_button_clicked()

    value = wdg.value()
    assert value.plate == data.plate
    assert value.wells == data.wells
    assert value.mode == data.mode

    assert value.calibration
    assert value.calibration.well_A1_center == (-0.0, -0.0)
    assert value.calibration.rotation_matrix == [[1.0, 0.0], [-0.0, 1.0]]
    assert (
        value.calibration.calibration_positions_a1
        == data.calibration.calibration_positions_a1
    )
    assert (
        value.calibration.calibration_positions_an
        == data.calibration.calibration_positions_an
    )


def test_hcs_wizard_fov_load(
    data: HCSData, global_mmcore: CMMCorePlus, qtbot: QtBot, database: dict[str, Plate]
):
    wdg = HCSWizard()
    qtbot.addWidget(wdg)

    wdg.setValue(data)

    rnd_value = wdg.fov_page._fov_widget.random_wdg.value()
    assert rnd_value.num_points == 3

    fov_view_value = wdg.fov_page._fov_widget.view.value()
    assert fov_view_value.mode.num_points == 3


def test_serialization(data: HCSData):
    _str = data.model_dump_json()
    new_data = HCSData(**json.loads(_str))
    assert new_data.plate == data.plate
    assert new_data.wells == data.wells
    assert new_data.mode == data.mode
    assert new_data.positions == data.positions
    assert new_data.calibration.rotation_matrix == data.calibration.rotation_matrix


def test_save_load_hcs(data: HCSData, qtbot: QtBot, tmp_path: Path):
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

        with patch.object(QFileDialog, "getOpenFileName", _path):
            wdg._load()

            value = wdg.value()
            assert value.plate == data.plate
            assert value.wells == data.wells
            assert value.mode == data.mode
            assert value.positions == data.positions
            assert value.calibration.rotation_matrix == data.calibration.rotation_matrix
