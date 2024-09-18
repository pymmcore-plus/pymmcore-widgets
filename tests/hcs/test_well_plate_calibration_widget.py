import useq
from pymmcore_plus import CMMCorePlus

from pymmcore_widgets.hcs._plate_calibration_widget import PlateCalibrationWidget
from pymmcore_widgets.useq_widgets._well_plate_widget import DATA_POSITION


def test_plate_calibration_value(global_mmcore: CMMCorePlus, qtbot) -> None:
    wdg = PlateCalibrationWidget(mmcore=global_mmcore)
    qtbot.addWidget(wdg)
    plan = useq.WellPlatePlan(plate="96-well", a1_center_xy=(10, 20), rotation=2)
    wdg.setValue(plan)
    assert wdg.value() == plan


def test_plate_calibration(global_mmcore: CMMCorePlus, qtbot) -> None:
    wdg = PlateCalibrationWidget(mmcore=global_mmcore)
    wdg.show()
    qtbot.addWidget(wdg)

    with qtbot.waitSignal(wdg.calibrationChanged) as sig:
        wdg.setValue(
            useq.WellPlatePlan(plate="24-well", a1_center_xy=(0, 0), rotation=2)
        )
    assert sig.args == [True]
    assert wdg.value().plate.rows == 4
    assert wdg._tab_wdg.isTabEnabled(1)

    with qtbot.waitSignal(wdg.calibrationChanged) as sig:
        wdg.setValue("96-well")
    assert sig.args == [False]
    assert wdg.value()
    assert wdg.value().plate.rows == 8
    assert not wdg._tab_wdg.isTabEnabled(1)

    with qtbot.waitSignal(wdg.calibrationChanged) as sig:
        wdg.setValue(useq.WellPlate.from_str("12-well"))
    assert sig.args == [False]
    assert wdg.value().plate.rows == 3
    assert not wdg._tab_wdg.isTabEnabled(1)

    ORIGIN = (10, 20)
    # first well
    wdg._plate_view.setSelectedIndices({(0, 0)})
    with qtbot.waitSignal(wdg.calibrationChanged) as sig:
        wdg._current_calibration_widget().setWellCenter(ORIGIN)
        assert sig.args == [False]
        assert not wdg._origin_spacing_rotation()
        assert not wdg._tab_wdg.isTabEnabled(1)

    # second well
    wdg._plate_view.setSelectedIndices({(0, 1)})
    with qtbot.waitSignal(wdg.calibrationChanged) as sig:
        wdg._current_calibration_widget().setWellCenter((ORIGIN[0] + 100, ORIGIN[1]))
        assert sig.args == [False]
        assert not wdg._origin_spacing_rotation()
        assert not wdg._tab_wdg.isTabEnabled(1)

    # third well (will now be calibrated)
    wdg._plate_view.setSelectedIndices({(1, 1)})
    with qtbot.waitSignal(wdg.calibrationChanged) as sig:
        wdg._current_calibration_widget().setWellCenter(
            (ORIGIN[0] + 100, ORIGIN[1] + 100)
        )
        assert sig.args == [True]
        assert wdg._tab_wdg.isTabEnabled(1)
    assert wdg._origin_spacing_rotation() is not None
    assert wdg.value().a1_center_xy == (ORIGIN)

    # clear third well, show that it becomes uncalibrated
    with qtbot.waitSignal(wdg.calibrationChanged) as sig:
        wdg._current_calibration_widget().setWellCenter(None)
        assert sig.args == [False]
        assert not wdg._tab_wdg.isTabEnabled(1)
    assert wdg._origin_spacing_rotation() is None


def test_plate_calibration_colinear(global_mmcore: CMMCorePlus, qtbot):
    wdg = PlateCalibrationWidget(mmcore=global_mmcore)
    wdg.show()
    qtbot.addWidget(wdg)
    wdg.setValue("24-well")

    spacing = 100
    for point in ((0, 0), (1, 1), (2, 2)):
        wdg._plate_view.setSelectedIndices({point})
        with qtbot.waitSignal(wdg.calibrationChanged):
            wdg._current_calibration_widget().setWellCenter(
                (point[0] * spacing, point[1] * spacing)
            )

    assert "Ensure points are not collinear" in wdg._info.text()
    wdg._plate_view.setSelectedIndices({(3, 2)})
    with qtbot.waitSignal(wdg.calibrationChanged):
        wdg._current_calibration_widget().setWellCenter((3 * spacing, 2 * spacing))

    assert "Ensure points are not collinear" not in wdg._info.text()


def test_plate_calibration_items(global_mmcore: CMMCorePlus, qtbot) -> None:
    wdg = PlateCalibrationWidget(mmcore=global_mmcore)
    wdg.show()
    qtbot.addWidget(wdg)

    scene = wdg._plate_view._scene
    scene_test = wdg._plate_test._scene

    # set the plan so that the plate is calibrated
    wdg.setValue(useq.WellPlatePlan(plate="96-well", a1_center_xy=(0, 0)))
    assert scene.items()
    # we should have 96 QGraphicsEllipseItem wells, each with a QGraphicsTextItem
    assert len(scene.items()) == 96 * 2

    assert scene_test.items()
    # we should have 96 QGraphicsEllipseItem wells, each with 5 HoverWellItem
    assert len(scene_test.items()) == 96 + (96 * 5)

    # we should not have any items in the test scene since not yet calibrated
    wdg.setValue("24-well")
    assert not scene_test.items()


def test_plate_calibration_well_test(global_mmcore: CMMCorePlus, qtbot) -> None:
    import math

    wdg = PlateCalibrationWidget(mmcore=global_mmcore)
    wdg.show()
    qtbot.addWidget(wdg)

    # circular plate
    wdg.setValue("96-well")
    well_wdg = wdg._current_calibration_widget()
    well_wdg.setWellCenter((100, 100))

    assert global_mmcore.getXPosition() == 0
    assert global_mmcore.getYPosition() == 0

    global_mmcore.waitForSystem()
    wdg._move_to_test_position()

    global_mmcore.waitForSystem()
    x, y = global_mmcore.getXYPosition()
    cx, cy = well_wdg.wellCenter()
    w, h = wdg.value().plate.well_size
    r = w * 1000 / 2
    distance_squared = (x - cx) ** 2 + (y - cy) ** 2
    # assert that the current position is on the circumference of the well
    assert math.isclose(distance_squared, r**2, abs_tol=100)

    # rectangular plate
    wdg.setValue("384-well")
    well_wdg = wdg._current_calibration_widget()
    well_wdg.setWellCenter((100, 100))

    global_mmcore.waitForSystem()
    wdg._move_to_test_position()

    global_mmcore.waitForSystem()
    x, y = global_mmcore.getXYPosition()
    cx, cy = well_wdg.wellCenter()
    w, h = wdg.value().plate.well_size
    w, h = w * 1000, h * 1000

    vertices = [
        (round(cx - w / 2), round(cy - h / 2)),  # top left
        (round(cx + w / 2), round(cy - h / 2)),  # top right
        (round(cx + w / 2), round(cy + h / 2)),  # bottom right
        (round(cx - w / 2), round(cy + h / 2)),  # bottom left
    ]
    # assert that the current position is one of the vertices
    assert (round(x), round(y)) in vertices


def test_plate_calibration_test_positions(global_mmcore: CMMCorePlus, qtbot) -> None:
    wdg = PlateCalibrationWidget(mmcore=global_mmcore)
    wdg.show()
    qtbot.addWidget(wdg)

    wdg.setValue(useq.WellPlatePlan(plate="96-well", a1_center_xy=(0, 0)))

    scene = wdg._plate_test._scene
    assert scene.items()

    hover_items = list(reversed(scene.items()))[96:101]
    expected_data = [
        (0, 0, "A1"),
        (-3200, 0, "A1"),
        (3200, 0, "A1"),
        (0, -3200, "A1"),
        (0, 3200, "A1"),
    ]
    data = []
    for hover_item in hover_items:
        hover_item_data = hover_item.data(DATA_POSITION)
        data.append((hover_item_data.x, hover_item_data.y, hover_item_data.name))

    assert data == expected_data
