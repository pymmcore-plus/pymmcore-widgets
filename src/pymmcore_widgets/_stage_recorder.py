from typing import Optional, Tuple

import numpy as np
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget
from skimage.transform import resize
from useq import MDAEvent
from vispy import scene
from vispy.visuals.transforms import STTransform


class StageRecorder(QWidget):
    """A stage positions viewer widget."""

    def __init__(
        self, parent: Optional[QWidget] = None, *, mmcore: Optional[CMMCorePlus] = None
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._preview_visuals: Tuple = ()
        self._mda_visuals: Tuple = ()
        self._mda_visuals_list: list = []

        self._x_range: Tuple = ()
        self._y_range: Tuple = ()

        self._create_gui()

        self._mmc.events.imageSnapped.connect(self._on_image_snapped)

    def _create_gui(self) -> None:

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)

        self.canvas = scene.SceneCanvas(keys="interactive", show=True)
        layout.addWidget(self.canvas.native)

        self.view = self.canvas.central_widget.add_view()
        self.view.camera = scene.PanZoomCamera(aspect=1)

        btns = QWidget()
        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(10)
        btns_layout.setContentsMargins(5, 5, 5, 5)
        btns.setLayout(btns_layout)
        # clear button
        self._clear_btn = QPushButton(text="Clear")
        self._clear_btn.clicked.connect(self._clear)
        # reset view button
        self._reset_view_btn = QPushButton(text="Reset View")
        self._reset_view_btn.clicked.connect(self._reset_view)
        btns_layout.addWidget(self._clear_btn)
        btns_layout.addWidget(self._reset_view_btn)

        layout.addWidget(btns)

    def _on_image_snapped(self) -> None:
        self._add_preview_to_viewer(self._mmc.getImage())

    def _add_preview_to_viewer(self, img: np.ndarray) -> None:

        _, _, w, h = self._mmc.getROI()

        _width = w / 2
        _height = h / 2

        scaled = resize(img, (_width, _height))

        scaled_8bit = (scaled / scaled.max()) * 255
        scaled_8bit = np.uint8(scaled_8bit)

        x = self._mmc.getXPosition()
        y = self._mmc.getYPosition()

        if len(self._preview_visuals) > 0:
            _, preview, _, _ = self._preview_visuals
            preview.set_data(scaled_8bit)
        else:
            preview = scene.visuals.Image(
                scaled_8bit, cmap="grays", parent=self.view.scene
            )

        self._preview_visuals = ("preview", preview, x, y)

        preview.transform = STTransform(translate=(x, y))

        self._x_range = (x, (x + _width))
        self._y_range = (y, (y + _width))

    def _add_from_mda(self, img: np.ndarray, event: MDAEvent) -> None:

        _, _, w, h = self._mmc.getROI()

        # _width = w / 2
        # _height = h / 2

        _width = w
        _height = h

        # scaled = resize(img, (_width, _height))

        # scaled_8bit = (scaled / scaled.max()) * 255
        # scaled_8bit = np.uint8(scaled_8bit)

        scaled_8bit = img

        x = event.x_pos
        y = event.y_pos

        if len(self._mda_visuals) > 0:

            _, mda, _x, _y = self._mda_visuals

            if x == _x and y == _y:
                mda.set_data(scaled_8bit)
            else:
                mda = scene.visuals.Image(
                    scaled_8bit, cmap="grays", parent=self.view.scene
                )
                self._mda_visuals_list.append(mda)
        else:
            mda = scene.visuals.Image(scaled_8bit, cmap="grays", parent=self.view.scene)

            self._mda_visuals_list.append(mda)

        self._mda_visuals = ("mda", mda, x, y)

        mda.transform = STTransform(translate=(x, y))

        self._x_range = (x, (x + _width))  # type: ignore
        self._y_range = (y, (y + _height))  # type: ignore

    def _clear(self) -> None:
        if not self._preview_visuals or not self._mda_visuals_list:
            return

        _, img, _, _ = self._preview_visuals
        img.parent = None
        self._preview_visuals = ()

        for vis in self._mda_visuals_list:
            vis.parent = None
        self._mda_visuals_list.clear()

    def _reset_view(self) -> None:
        self.view.camera.set_range(x=self._x_range, y=self._y_range)
