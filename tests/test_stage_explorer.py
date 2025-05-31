from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from vispy.app.canvas import MouseEvent
from vispy.scene.visuals import Image

from pymmcore_widgets.control._stage_explorer import _stage_explorer
from pymmcore_widgets.control._stage_explorer._stage_explorer import StageExplorer
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
    stage_viewer.global_autoscale(ignore_min=0.1, ignore_max=0.1)
    stage_viewer.set_colormap("viridis")


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

    actions = explorer.toolBar().actions()
    snap_action = next(a for a in actions if a.text() == _stage_explorer.SNAP)
    assert explorer.snap_on_double_click is True
    with qtbot.waitSignal(snap_action.triggered):
        snap_action.trigger()
    assert explorer.snap_on_double_click is False

    auto_action = explorer._actions[_stage_explorer.AUTO_ZOOM_TO_FIT]
    auto_action.trigger()
    assert explorer.auto_zoom_to_fit
    # this turns it off
    explorer._actions[_stage_explorer.ZOOM_TO_FIT].trigger()
    assert not explorer.auto_zoom_to_fit

    assert not explorer._stage_viewer._grid_lines.visible
    grid_action = explorer._actions[_stage_explorer.SHOW_GRID]
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

    poll_action = explorer._actions[_stage_explorer.POLL_STAGE]
    assert explorer._poll_stage_position is True
    assert explorer._timer_id is not None

    # wait for timerEvent to be triggered
    qtbot.waitUntil(lambda: explorer._stage_pos_marker is not None, timeout=1000)
    assert explorer._stage_pos_marker is not None
    assert explorer._stage_pos_marker.visible

    with qtbot.waitSignal(poll_action.triggered):
        poll_action.trigger()

    assert explorer._poll_stage_position is False
    assert explorer._stage_pos_marker is None
    assert explorer._timer_id is None


def test_mouse_hover_shows_position(qtbot: QtBot) -> None:
    viewer = StageViewer()
    viewer.show()
    qtbot.addWidget(viewer)
    viewer.set_hover_label_visible(True)

    # Simulate mouse move event
    event = MouseEvent("mouse_move", pos=(100, 2))
    viewer._on_mouse_move(event)

    # Check if the hover label is visible and shows the correct position
    assert viewer._hover_pos_label.isVisible()
    assert viewer._hover_pos_label.text().startswith("(")
