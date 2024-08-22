import useq
from pymmcore_plus import CMMCorePlus

from pymmcore_widgets.hcs._plate_calibration_widget import PlateCalibrationWidget


def test_plate_calibration(global_mmcore: CMMCorePlus, qtbot) -> None:
    w = PlateCalibrationWidget(mmcore=global_mmcore)
    w.show()
    qtbot.addWidget(w)

    w.setPlate("96-well")
    assert w.platePlan().plate.rows == 8
    w.setPlate(useq.WellPlate.from_str("12-well"))
    assert w.platePlan().plate.rows == 3
    w.setPlate(useq.WellPlatePlan(plate="24-well", a1_center_xy=(0, 0)))
    assert w.platePlan().plate.rows == 4

    ORIGIN = (10, 20)
    # first well
    w._plate_view.setSelectedIndices({(0, 0)})
    with qtbot.waitSignal(w.calibrationChanged):
        w._current_calibration_widget().setWellCenter(ORIGIN)
        assert not w._origin_spacing_rotation()

    # second well
    w._plate_view.setSelectedIndices({(0, 1)})
    with qtbot.waitSignal(w.calibrationChanged):
        w._current_calibration_widget().setWellCenter((ORIGIN[0] + 100, ORIGIN[1]))
        assert not w._origin_spacing_rotation()

    # third well (will now be calibrated)
    w._plate_view.setSelectedIndices({(1, 1)})
    with qtbot.waitSignal(w.calibrationChanged):
        w._current_calibration_widget().setWellCenter(
            (ORIGIN[0] + 100, ORIGIN[1] + 100)
        )
    assert w._origin_spacing_rotation() is not None
    assert w.platePlan().a1_center_xy == (ORIGIN)

    # clear third well, show that it becomes uncalibrated
    with qtbot.waitSignal(w.calibrationChanged):
        w._current_calibration_widget().setWellCenter(None)
    assert w._origin_spacing_rotation() is None


def test_plate_calibration_colinear(global_mmcore: CMMCorePlus, qtbot):
    w = PlateCalibrationWidget(mmcore=global_mmcore)
    w.show()
    qtbot.addWidget(w)
    w.setPlate("24-well")

    spacing = 100
    for point in ((0, 0), (1, 1), (2, 2)):
        w._plate_view.setSelectedIndices({point})
        with qtbot.waitSignal(w.calibrationChanged):
            w._current_calibration_widget().setWellCenter(
                (point[0] * spacing, point[1] * spacing)
            )

    assert "Ensure points are not collinear" in w._info.text()
    w._plate_view.setSelectedIndices({(3, 2)})
    with qtbot.waitSignal(w.calibrationChanged):
        w._current_calibration_widget().setWellCenter((3 * spacing, 2 * spacing))

    assert "Ensure points are not collinear" not in w._info.text()
