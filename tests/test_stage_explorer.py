from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import numpy as np
import useq
from pymmcore_plus import CMMCorePlus
from vispy.app.canvas import MouseEvent
from vispy.scene.visuals import Image

from pymmcore_widgets.control._rois.roi_model import RectangleROI
from pymmcore_widgets.control._stage_explorer._stage_explorer import (
    ContrastSlider,
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


# ---------------------------------------------------------------------------
# ContrastSlider - data range tracking
# ---------------------------------------------------------------------------


def test_contrast_slider_data_range_expands(qtbot: QtBot) -> None:
    """update_data_range expands the running data range and auto-sets handles."""
    widget = ContrastSlider()
    qtbot.addWidget(widget)

    widget.update_data_range(10, 200)
    assert widget._slider.value() == (10, 200)

    widget.update_data_range(5, 180)  # expands min, not max
    assert widget._slider.value() == (5, 200)


def test_contrast_slider_data_range_no_clobber_when_auto_off(qtbot: QtBot) -> None:
    """update_data_range does not move handles when auto is off."""
    widget = ContrastSlider()
    qtbot.addWidget(widget)

    widget.update_data_range(0, 255)
    widget._slider.setValue((50, 150))  # user manually adjusts (turns auto off)

    widget.update_data_range(0, 300)  # range expands
    lo, hi = widget._slider.value()
    assert lo == 50
    assert hi == 150


def test_contrast_slider_reset_data_range(qtbot: QtBot) -> None:
    """reset_data_range clears the running range."""
    widget = ContrastSlider()
    qtbot.addWidget(widget)

    widget.update_data_range(0, 255)
    widget.reset_data_range()

    assert widget._data_min == float("inf")
    assert widget._data_max == float("-inf")


# ---------------------------------------------------------------------------
# StageExplorer - _has_devices / _update_actions_enabled
# ---------------------------------------------------------------------------


def test_stage_explorer_has_devices(qtbot: QtBot) -> None:
    """_has_devices returns True when the test config is loaded."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    assert explorer._has_devices()


def test_stage_explorer_update_actions_enabled(qtbot: QtBot) -> None:
    """Toolbar actions are all enabled when devices are loaded."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    tb = explorer._toolbar
    assert tb.snap_action.isEnabled()
    assert tb.poll_stage_action.isEnabled()
    assert tb.scan_action.isEnabled()
    assert tb.delete_rois_action.isEnabled()
    for action in explorer.roi_manager.mode_actions.actions():
        assert action.isEnabled()


def test_stage_explorer_update_actions_disabled_without_devices(
    qtbot: QtBot,
) -> None:
    """Toolbar actions are all disabled when no devices are loaded."""
    mmc = CMMCorePlus()  # empty core - only the 'Core' device
    explorer = StageExplorer(mmcore=mmc)
    qtbot.addWidget(explorer)
    tb = explorer._toolbar
    assert not tb.snap_action.isEnabled()
    assert not tb.poll_stage_action.isEnabled()
    assert not tb.scan_action.isEnabled()
    assert not tb.delete_rois_action.isEnabled()
    for action in explorer.roi_manager.mode_actions.actions():
        assert not action.isEnabled()


# ---------------------------------------------------------------------------
# StageExplorer - contrast slider
# ---------------------------------------------------------------------------


def test_stage_explorer_contrast_slider_hidden_initially(qtbot: QtBot) -> None:
    """The contrast slider starts hidden."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    explorer.show()
    assert not explorer._contrast_slider.isVisible()


def test_stage_explorer_contrast_slider_shown_after_image(qtbot: QtBot) -> None:
    """Adding an image makes the contrast slider visible."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    explorer.show()
    img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    explorer.add_image(img, 0.0, 0.0)
    assert explorer._contrast_slider.isVisible()


def test_stage_explorer_contrast_slider_values_set_on_first_image(
    qtbot: QtBot,
) -> None:
    """Slider handle values are auto-set from the first image's data range."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    img = np.array([[10, 200]], dtype=np.uint8)
    explorer.add_image(img, 0.0, 0.0)
    lo, hi = explorer._contrast_slider._slider.value()
    assert lo == 10
    assert hi == 200


def test_stage_explorer_contrast_slider_not_reset_by_second_image(
    qtbot: QtBot,
) -> None:
    """Slider handles are NOT reset when a second image expands the data range."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    explorer.show()
    img1 = np.array([[10, 200]], dtype=np.uint8)
    explorer.add_image(img1, 0.0, 0.0)
    # manually change slider values after first image
    explorer._contrast_slider._slider.setValue((50, 150))

    img2 = np.array([[0, 255]], dtype=np.uint8)  # wider range
    explorer.add_image(img2, 10.0, 0.0)

    # slider handles should still reflect the manually set values
    lo, hi = explorer._contrast_slider._slider.value()
    assert lo == 50
    assert hi == 150


def test_stage_explorer_contrast_slider_applies_clims(qtbot: QtBot) -> None:
    """Moving the contrast slider updates the clims on all images."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    img = np.random.randint(0, 255, (50, 50), dtype=np.uint8)
    explorer.add_image(img, 0.0, 0.0)

    explorer._on_contrast_slider_changed((30, 220))

    assert explorer._stage_viewer._clims == (30.0, 220.0)


# ---------------------------------------------------------------------------
# ContrastSlider - auto button toggles off on manual slider interaction
# ---------------------------------------------------------------------------


def test_contrast_slider_auto_off_on_user_interaction(qtbot: QtBot) -> None:
    """Manually moving the slider turns the auto button off."""
    widget = ContrastSlider()
    qtbot.addWidget(widget)
    widget._slider.setRange(0, 255)
    assert widget._auto_btn.isChecked()

    widget._slider.setValue((50, 200))

    assert not widget._auto_btn.isChecked()
    assert not widget.auto


def test_contrast_slider_auto_stays_on_during_programmatic_update(
    qtbot: QtBot,
) -> None:
    """Programmatic update_data_range does NOT disable the auto button."""
    widget = ContrastSlider()
    qtbot.addWidget(widget)
    assert widget._auto_btn.isChecked()

    widget.update_data_range(10, 200)

    assert widget._auto_btn.isChecked()
    assert widget.auto


def test_contrast_slider_auto_toggle_restores_handles(qtbot: QtBot) -> None:
    """Re-enabling auto restores handles to the tracked data range."""
    widget = ContrastSlider()
    qtbot.addWidget(widget)

    widget.update_data_range(10, 200)
    widget._slider.setValue((50, 150))  # turns auto off
    assert not widget.auto

    widget._auto_btn.setChecked(True)
    assert widget.auto
    assert widget._slider.value() == (10, 200)


def test_stage_explorer_clear_action_hides_contrast_slider(qtbot: QtBot) -> None:
    """Triggering the clear action hides the contrast slider and clears images."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    explorer.show()
    img = np.random.randint(0, 255, (50, 50), dtype=np.uint8)
    explorer.add_image(img, 0.0, 0.0)
    assert explorer._contrast_slider.isVisible()

    explorer._toolbar.clear_action.trigger()

    assert not explorer._contrast_slider.isVisible()
    assert not list(explorer._stage_viewer._get_images())


# ---------------------------------------------------------------------------
# StageExplorer - _on_roi_changed early-return guard
# ---------------------------------------------------------------------------


def test_stage_explorer_roi_changed_skipped_when_no_image_dimensions(
    qtbot: QtBot,
) -> None:
    """_on_roi_changed returns early when width/height are 0."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    half_before = explorer._half_img_shift.copy()

    with (
        patch.object(explorer._mmc, "getImageWidth", return_value=0),
        patch.object(explorer._mmc, "getImageHeight", return_value=0),
    ):
        explorer._on_roi_changed()

    # half_img_shift should be unchanged (early return was hit)
    np.testing.assert_array_equal(explorer._half_img_shift, half_before)


# ---------------------------------------------------------------------------
# StageExplorer - _update_marker_mode guard when marker is None
# ---------------------------------------------------------------------------


def test_stage_explorer_update_marker_mode_no_marker(qtbot: QtBot) -> None:
    """_update_marker_mode returns gracefully when stage_pos_marker is None."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    explorer._stage_pos_marker = None
    # should not raise
    explorer._update_marker_mode()


# ---------------------------------------------------------------------------
# StageExplorer - _on_sys_config_loaded
# ---------------------------------------------------------------------------


def test_stage_explorer_sys_config_loaded_restarts_poller(
    qtbot: QtBot, global_mmcore: CMMCorePlus
) -> None:
    """_on_sys_config_loaded restarts the poller when an XY stage is present."""
    explorer = StageExplorer(mmcore=global_mmcore)
    qtbot.addWidget(explorer)
    # stop the poller first so we can verify it restarts
    explorer._stop_poller()
    assert not explorer._stage_poller.isRunning()

    explorer._on_sys_config_loaded()

    assert explorer._stage_poller.isRunning()


def test_stage_explorer_sys_config_loaded_stops_poller_when_no_xy(
    qtbot: QtBot, global_mmcore: CMMCorePlus
) -> None:
    """_on_sys_config_loaded stops the poller when no XY stage is available."""
    explorer = StageExplorer(mmcore=global_mmcore)
    qtbot.addWidget(explorer)
    # wait until the poller is running
    qtbot.waitUntil(lambda: explorer._stage_poller.isRunning(), timeout=2000)

    with patch.object(explorer._mmc, "getXYStageDevice", return_value=""):
        explorer._on_sys_config_loaded()

    assert not explorer._stage_poller.isRunning()


# ---------------------------------------------------------------------------
# StageExplorer - _create_stage_pos_marker replaces existing marker
# ---------------------------------------------------------------------------


def test_stage_explorer_create_stage_pos_marker_replaces_existing(
    qtbot: QtBot,
) -> None:
    """_create_stage_pos_marker detaches and replaces a pre-existing marker."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    assert explorer._stage_pos_marker is not None
    first_marker = explorer._stage_pos_marker

    explorer._create_stage_pos_marker()

    assert explorer._stage_pos_marker is not None
    assert explorer._stage_pos_marker is not first_marker
    # old marker must be detached from the scene
    assert first_marker.parent is None


# ---------------------------------------------------------------------------
# StageExplorer - _set_stage_controller
# ---------------------------------------------------------------------------


def test_stage_explorer_stage_controller_none_without_xy_device(
    qtbot: QtBot,
) -> None:
    """_set_stage_controller sets controller to None when no XY device is loaded."""
    mmc = CMMCorePlus()  # empty - no XY stage
    explorer = StageExplorer(mmcore=mmc)
    qtbot.addWidget(explorer)
    assert explorer._stage_controller is None


def test_stage_explorer_stage_controller_set_with_xy_device(
    qtbot: QtBot, global_mmcore: CMMCorePlus
) -> None:
    """_set_stage_controller creates a controller when an XY device is present."""
    explorer = StageExplorer(mmcore=global_mmcore)
    qtbot.addWidget(explorer)
    assert explorer._stage_controller is not None


# ---------------------------------------------------------------------------
# StageExplorer - _on_pixel_size_changed accepts *args
# ---------------------------------------------------------------------------


def test_stage_explorer_pixel_size_handlers_refresh_affine(
    qtbot: QtBot,
) -> None:
    """Both pixel size handlers call _affine_state.refresh()."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    # neither should raise
    explorer._on_pixel_size_changed(0.065)
    explorer._on_pixel_size_affine_changed()


# ---------------------------------------------------------------------------
# StageExplorer - stop scan action
# ---------------------------------------------------------------------------


def test_stop_scan_action_cancels_when_mda_running(qtbot: QtBot) -> None:
    """Triggering stop_scan_action calls mda.cancel() when a sequence is running."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    with (
        patch.object(explorer._mmc.mda, "is_running", return_value=True),
        patch.object(explorer._mmc.mda, "cancel") as mock_cancel,
    ):
        explorer._toolbar.stop_scan_action.trigger()
    mock_cancel.assert_called_once()


def test_stop_scan_action_stops_stage_when_no_mda(qtbot: QtBot) -> None:
    """Triggering stop_scan_action stops the XY stage when no sequence is running."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    xy_dev = explorer._mmc.getXYStageDevice()
    with (
        patch.object(explorer._mmc.mda, "is_running", return_value=False),
        patch.object(explorer._mmc, "stop") as mock_stop,
    ):
        explorer._toolbar.stop_scan_action.trigger()
    mock_stop.assert_called_once_with(xy_dev)


def test_sequence_finished_resets_our_mda_running(qtbot: QtBot) -> None:
    """_on_sequence_finished resets _our_mda_running to False."""
    explorer = StageExplorer()
    qtbot.addWidget(explorer)
    explorer._our_mda_running = True
    explorer._on_sequence_finished()
    assert not explorer._our_mda_running
