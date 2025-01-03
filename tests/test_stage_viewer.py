from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from vispy.scene.visuals import Image

from pymmcore_widgets.control._stage_explorer._stage_viewer import StageViewer

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_add_image(qtbot: QtBot):
    stage_viewer = StageViewer()
    qtbot.addWidget(stage_viewer)
    img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    stage_viewer.add_image(img, 150, 300)
    # assert translated position is in the image store
    assert (100, 250) in stage_viewer.image_store
    assert np.array_equal(stage_viewer.image_store[(100, 250)], img)


def test_clear_scene(qtbot: QtBot):
    stage_viewer = StageViewer()
    qtbot.addWidget(stage_viewer)
    img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    stage_viewer.add_image(img, 150, 300)
    stage_viewer.clear_scene()
    assert not stage_viewer.image_store
    assert not [i for i in stage_viewer.view.scene.children if isinstance(i, Image)]


def test_reset_view(qtbot: QtBot):
    stage_viewer = StageViewer()
    qtbot.addWidget(stage_viewer)
    img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    stage_viewer.add_image(img, 150, 300)
    stage_viewer.reset_view()
    assert stage_viewer.view.camera.rect.center == (150, 300)


def test_update_by_scale(qtbot: QtBot):
    stage_viewer = StageViewer()
    qtbot.addWidget(stage_viewer)
    img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    stage_viewer.add_image(img, 150, 300)
    initial_scale = stage_viewer.get_scale()
    stage_viewer.update_by_scale(initial_scale * 2)
    image = next(i for i in stage_viewer.view.scene.children if isinstance(i, Image))
    assert (image.transform.scale[0], image.transform.scale[1]) == (initial_scale * 2, initial_scale * 2)


def test_pixel_size_property(qtbot: QtBot):
    stage_viewer = StageViewer()
    qtbot.addWidget(stage_viewer)
    stage_viewer.pixel_size = 2.0
    assert stage_viewer.pixel_size == 2.0
