from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import useq
from vispy.app.canvas import MouseEvent
from vispy.scene.visuals import Image

from pymmcore_widgets.control._rois.roi_model import RectangleROI
from pymmcore_widgets.control._stage_explorer._stage_explorer import (
    ScanMenu,
    StageExplorer,
)
from pymmcore_widgets.control._stage_explorer._stage_viewer import StageViewer

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

IMG = np.random.randint(0, 255, (100, 50), dtype=np.uint8)


def _build_transform_matrix(x: float, y: float) -> np.ndarray:
    T = np.eye(4)
    T[0, 3] += x
    T[1, 3] += y
    return T


def test_stage_viewer_add_image(qtbot: QtBot) -> None:
    stage_viewer = StageViewer()
    qtbot.addWidget(stage_viewer)
    T = _build_transform_matrix(100, 150)
    stage_viewer.add_image(IMG, T.T)
    images = [i for i in stage_viewer.view.scene.children if isinstance(i, Image)]
    assert len(images) == 1
    added_img = next(iter(images))
    assert tuple(added_img.transform.matrix[3, :2]) == (100, 150)


def test_stage_viewer_clims_cmaps(qtbot: QtBot) -> None:
    stage_viewer = StageViewer()
    qtbot.addWidget(stage_viewer)
    T = _build_transform_matrix(100, 150)
    stage_viewer.add_image(IMG, T.T)

    # just some smoke tests
    stage_viewer.set_clims((0, 1))


def test_stage_viewer_clear_scene(qtbot: QtBot) -> None:
    stage_viewer = StageViewer()
    qtbot.addWidget(stage_viewer)
    T = _build_transform_matrix(200, 50)
    stage_viewer.add_image(IMG, T.T)
    assert [i for i in stage_viewer.view.scene.children if isinstance(i, Image)]
    stage_viewer.clear()
    assert not [i for i in stage_viewer.view.scene.children if isinstance(i, Image)]


def test_stage_viewer_reset_view(qtbot: QtBot) -> None:
    stage_viewer = StageViewer()
    qtbot.addWidget(stage_viewer)
    T = _build_transform_matrix(500, 100)
    stage_viewer.add_image(IMG, T.T)
    stage_viewer.zoom_to_fit()
    cx, cy = stage_viewer.view.camera.rect.center
    assert round(cx) == 525  # image width is 50, center should be Tx + width/2
    assert round(cy) == 150  # image height is 100, center should be Ty + height/2


def test_stage_explorer_initialization(qtbot: QtBot) -> None:
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    assert explorer.windowTitle() == "Stage Explorer"
    assert explorer.snap_on_double_click is True


def test_stage_explorer_snap_on_double_click(qtbot: QtBot) -> None:
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    explorer.snap_on_double_click = True
    assert explorer.snap_on_double_click is True
    explorer.snap_on_double_click = False
    assert explorer.snap_on_double_click is False


def test_stage_explorer_add_image(qtbot: QtBot) -> None:
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    image = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    stage_x, stage_y = 50.0, 75.0
    explorer.add_image(image, stage_x, stage_y)
    # Verify the image was added to the stage viewer
    nimages = len(list(explorer._stage_viewer._get_images()))
    assert nimages == 1


def test_stage_explorer_actions(qtbot: QtBot) -> None:
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    explorer.add_image(IMG, 0, 0)

    snap_action = explorer._toolbar.snap_action
    assert explorer.snap_on_double_click is True
    with qtbot.waitSignal(snap_action.triggered):
        snap_action.trigger()
    assert explorer.snap_on_double_click is False

    auto_action = explorer._toolbar.auto_zoom_to_fit_action
    auto_action.trigger()
    assert explorer.auto_zoom_to_fit
    # this turns it off
    explorer._toolbar.zoom_to_fit_action.trigger()
    assert not explorer.auto_zoom_to_fit

    assert not explorer._stage_viewer._grid_lines.visible
    grid_action = explorer._toolbar.show_grid_action
    grid_action.trigger()
    assert explorer._stage_viewer._grid_lines.visible


def test_stage_explorer_move_on_click(qtbot: QtBot) -> None:
    explorer = StageExplorer()
    qtbot.addWidget(explorer)

    explorer.add_image(IMG, 0, 0)
    stage_pos = explorer._mmc.getXYPosition()

    explorer._snap_on_double_click = True
    event = MouseEvent("mouse_press", pos=(100, 100), button=1)
    with qtbot.waitSignal(explorer._mmc.events.imageSnapped):
        explorer._on_mouse_double_click(event)

    assert explorer._mmc.getXYPosition() != stage_pos


def test_stage_explorer_position_indicator(qtbot: QtBot) -> None:
    explorer = StageExplorer()
    qtbot.addWidget(explorer)

    poll_action = explorer._toolbar.poll_stage_action
    assert explorer._poll_stage_position is True
    assert explorer._stage_poller.isRunning()

    # wait for the poller to emit at least once
    qtbot.waitUntil(lambda: explorer._stage_pos_marker is not None, timeout=1000)
    assert explorer._stage_pos_marker is not None
    assert explorer._stage_pos_marker.visible

    with qtbot.waitSignal(poll_action.triggered):
        poll_action.trigger()

    assert explorer._poll_stage_position is False
    assert not explorer._stage_poller.isRunning()


def test_mouse_hover_shows_position(qtbot: QtBot) -> None:
    viewer = StageViewer()
    viewer.show()
    qtbot.addWidget(viewer)

    # Simulate mouse move event
    event = MouseEvent("mouse_move", pos=(100, 2))
    viewer._on_mouse_move(event)

    # Check if the hover label is visible and shows the correct position
    assert viewer._hover_pos_label.isVisible()
    assert viewer._hover_pos_label.text().startswith("(")


# ---------------------------------------------------------------------------
# ScanMenu
# ---------------------------------------------------------------------------


def test_scan_menu_default_value(qtbot: QtBot) -> None:
    menu = ScanMenu()
    qtbot.addWidget(menu)
    overlap, mode = menu.value()
    assert overlap == 0.0
    assert mode == useq.OrderMode.spiral


def test_scan_menu_value_changed_signal(qtbot: QtBot) -> None:
    menu = ScanMenu()
    qtbot.addWidget(menu)
    with qtbot.waitSignal(menu.valueChanged):
        menu._overlap_spin.setValue(10.0)
    assert menu.value()[0] == 10.0


def test_scan_menu_mode_change(qtbot: QtBot) -> None:
    menu = ScanMenu()
    qtbot.addWidget(menu)
    with qtbot.waitSignal(menu.valueChanged):
        menu._mode_cbox.setCurrentEnum(useq.OrderMode.row_wise_snake)
    assert menu.value()[1] == useq.OrderMode.row_wise_snake


# ---------------------------------------------------------------------------
# StageExplorer - scan options propagation
# ---------------------------------------------------------------------------


def test_scan_options_propagate_to_manager(qtbot: QtBot) -> None:
    """Changing scan menu options updates overlap/mode on the ROI manager."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)

    explorer._on_scan_options_changed((5.0, useq.OrderMode.spiral))

    assert explorer.roi_manager.scan_overlap == 5.0
    assert explorer.roi_manager.scan_mode == useq.OrderMode.spiral


def test_scan_options_available_via_manager(qtbot: QtBot) -> None:
    """ROI manager exposes scan settings for use when building positions."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)

    explorer._toolbar.scan_menu._overlap_spin.setValue(3.0)
    explorer._toolbar.scan_menu._mode_cbox.setCurrentEnum(useq.OrderMode.spiral)

    assert explorer.roi_manager.scan_overlap == 3.0
    assert explorer.roi_manager.scan_mode == useq.OrderMode.spiral


# ---------------------------------------------------------------------------
# roi_manager - all_rois / selected_rois
# ---------------------------------------------------------------------------


def test_all_rois(qtbot: QtBot) -> None:
    explorer = StageExplorer()
    qtbot.addWidget(explorer)

    assert explorer.roi_manager.all_rois() == []

    roi_a = RectangleROI((0, 0), (10, 10), fov_size=(5.0, 5.0))
    roi_b = RectangleROI((20, 20), (30, 30), fov_size=(5.0, 5.0))
    explorer.roi_manager.add_roi(roi_a)
    explorer.roi_manager.add_roi(roi_b)
    assert explorer.roi_manager.all_rois() == [roi_a, roi_b]


def test_selected_rois(qtbot: QtBot) -> None:
    explorer = StageExplorer()
    qtbot.addWidget(explorer)

    roi = RectangleROI((0, 0), (10, 10), fov_size=(5.0, 5.0))
    explorer.roi_manager.add_roi(roi)
    assert explorer.roi_manager.selected_rois() == []

    explorer.roi_manager.select_roi(roi)
    assert explorer.roi_manager.selected_rois() == [roi]
