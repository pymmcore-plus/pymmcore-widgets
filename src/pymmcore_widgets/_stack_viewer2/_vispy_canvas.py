from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any

import cmap
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QVBoxLayout, QWidget
from vispy import scene

if TYPE_CHECKING:
    import numpy as np
    from vispy.scene.events import SceneMouseEvent


class VispyImageHandle:
    def __init__(self, image: scene.visuals.Image) -> None:
        self._image = image

    @property
    def data(self) -> np.ndarray:
        return self._image._data  # type: ignore

    @data.setter
    def data(self, data: np.ndarray) -> None:
        self._image.set_data(data)

    @property
    def visible(self) -> bool:
        return bool(self._image.visible)

    @visible.setter
    def visible(self, visible: bool) -> None:
        self._image.visible = visible

    @property
    def clim(self) -> Any:
        return self._image.clim

    @clim.setter
    def clim(self, clims: tuple[float, float]) -> None:
        self._image.clim = clims

    @property
    def cmap(self) -> cmap.Colormap:
        return cmap.Colormap(self._image.cmap)

    @cmap.setter
    def cmap(self, cmap: cmap.Colormap) -> None:
        self._image.cmap = cmap.to_vispy()


class VispyViewerCanvas(QWidget):
    """Vispy-based viewer for data.

    All vispy-specific code is encapsulated in this class (and non-vispy canvases
    could be swapped in if needed as long as they implement the same interface).
    """

    infoText = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._canvas = scene.SceneCanvas(parent=self)
        self._canvas.events.mouse_move.connect(self._on_mouse_move)
        self._camera = scene.PanZoomCamera(aspect=1, flip=(0, 1))

        central_wdg: scene.Widget = self._canvas.central_widget
        self._view: scene.ViewBox = central_wdg.add_view(camera=self._camera)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas.native)

    def refresh(self) -> None:
        self._canvas.update()

    def add_image(
        self, data: np.ndarray | None = None, cmap: cmap.Colormap | None = None
    ) -> VispyImageHandle:
        """Add a new Image node to the scene."""
        if cmap is not None:
            cmap = cmap.to_vispy()
        img = scene.visuals.Image(data, cmap=cmap, parent=self._view.scene)
        img.set_gl_state("additive", depth_test=False)
        img.interactive = True
        self.set_range()
        return VispyImageHandle(img)

    def set_range(
        self,
        x: tuple[float, float] | None = None,
        y: tuple[float, float] | None = None,
        margin: float | None = 0.05,
    ) -> None:
        """Update the range of the PanZoomCamera.

        When called with no arguments, the range is set to the full extent of the data.
        """
        self._camera.set_range(x=x, y=y, margin=margin)

    def _on_mouse_move(self, event: SceneMouseEvent) -> None:
        """Mouse moved on the canvas, display the pixel value and position."""
        images = []
        # Get the images the mouse is over
        seen = set()
        while visual := self._canvas.visual_at(event.pos):
            if isinstance(visual, scene.visuals.Image):
                images.append(visual)
            visual.interactive = False
            seen.add(visual)
        for visual in seen:
            visual.interactive = True
        if not images:
            return

        tform = images[0].get_transform("canvas", "visual")
        px, py, *_ = (int(x) for x in tform.map(event.pos))
        text = f"[{py}, {px}]"
        for c, img in enumerate(images):
            with suppress(IndexError):
                text += f" c{c}: {img._data[py, px]}"
        self.infoText.emit(text)
